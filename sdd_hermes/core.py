"""Durable, repository-local state for Hermes SDD.

The ledger is intentionally independent from Hermes' Kanban database.  Hermes owns
worker lifecycle and board transitions; this package owns the evidence needed to
decide whether a local result is actually acceptable.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import sqlite3
import subprocess
import time
import uuid
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = 6
DEFAULT_LIMITS = {"max_workers": 3, "max_repairs": 2, "max_provider_recoveries": 2, "max_native_retries": 3, "max_runtime_seconds": 3600, "max_total_runtime_seconds": 3600, "estimated_runtime_seconds": 300}


class SDDError(RuntimeError):
    """An actionable SDD workflow error."""


def utc_now() -> int:
    return int(time.time())


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def slugify(value: str) -> str:
    value = "-".join(value.strip().lower().split())
    value = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in value)
    while "--" in value:
        value = value.replace("--", "-")
    return value.strip("-")[:60] or "project"


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @property
    def runtime(self) -> Path:
        return self.root / ".sdd" / "hermes"

    @property
    def database(self) -> Path:
        return self.runtime / "ledger.sqlite3"

    @property
    def jsonl(self) -> Path:
        return self.runtime / "ledger.jsonl"

    @property
    def features(self) -> Path:
        return self.root / "docs" / "sdd" / "features"

    def prepare(self) -> None:
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.features.mkdir(parents=True, exist_ok=True)


def safe_relative(root: Path, raw: str) -> str:
    candidate = Path(raw)
    if candidate.is_absolute():
        raise SDDError(f"absolute paths are not valid ownership paths: {raw}")
    normalized = (root / candidate).resolve()
    try:
        relative = normalized.relative_to(root.resolve())
    except ValueError as exc:
        raise SDDError(f"path escapes repository: {raw}") from exc
    if str(relative) in ("", "."):
        raise SDDError("repository root cannot be owned")
    return relative.as_posix()


def file_fingerprint(root: Path, paths: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(set(paths)):
        path = root / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        if path.is_file():
            digest.update(path.read_bytes())
        else:
            digest.update(b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()


def repository_fingerprint(root: Path) -> str:
    paths: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(".git/") or relative.startswith(".sdd/hermes/"):
            continue
        paths.append(relative)
    return file_fingerprint(root, paths)


class Ledger:
    """SQLite ledger with append-only attempts/evidence and transactional writes."""

    def __init__(self, paths: ProjectPaths):
        self.paths = paths
        # Refuse future schemas before WAL setup, DDL, or directory creation.
        if self.paths.database.exists():
            with closing(sqlite3.connect(self.paths.database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
                self._schema_version(db)
        self.paths.prepare()
        self._init_database()

    @staticmethod
    def _schema_version(db) -> int:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'metadata'").fetchone():
            return 0
        row = db.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()
        version = int(row[0]) if row else 0
        if version > SCHEMA_VERSION:
            raise SDDError("ledger was written by a newer plugin; upgrade before continuing")
        return version

    @staticmethod
    def _execute_schema(db, script: str) -> None:
        # executescript() implicitly commits; execute complete statements instead
        # so schema changes and the version stamp share the migration transaction.
        statement = ''
        for line in script.splitlines(keepends=True):
            statement += line
            if sqlite3.complete_statement(statement):
                db.execute(statement)
                statement = ''
        if statement.strip():
            raise SDDError('incomplete schema statement')

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.paths.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _init_database(self) -> None:
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            version = self._schema_version(db)
            if version and version < SCHEMA_VERSION:
                # A separate reader sees the committed snapshot while this
                # connection holds the writer lock. Include committed WAL data.
                backup = self.paths.database.with_name(f'ledger.pre-v{SCHEMA_VERSION}-{uuid.uuid4().hex}.sqlite3')
                with closing(sqlite3.connect(self.paths.database.resolve().as_uri() + '?mode=ro', uri=True)) as source:
                    with closing(sqlite3.connect(backup)) as destination:
                        source.backup(destination)
            self._execute_schema(db,
                """
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY, root TEXT NOT NULL UNIQUE,
                    board_slug TEXT NOT NULL, stage TEXT NOT NULL, paused INTEGER NOT NULL DEFAULT 0,
                    limits_json TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS specs (
                    spec_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                    slug TEXT NOT NULL, revision INTEGER NOT NULL, mode TEXT NOT NULL,
                    request TEXT NOT NULL, content_json TEXT NOT NULL, created_at INTEGER NOT NULL,
                    UNIQUE(project_id, slug, revision)
                );
                CREATE TABLE IF NOT EXISTS request_repositories (
                    project_id TEXT PRIMARY KEY REFERENCES projects(project_id),
                    root TEXT NOT NULL, spec_path TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS active_requests (
                    root TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL UNIQUE REFERENCES projects(project_id)
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                    stable_key TEXT NOT NULL, title TEXT NOT NULL, role TEXT NOT NULL, kind TEXT NOT NULL,
                    status TEXT NOT NULL, spec_revision INTEGER NOT NULL, native_task_id TEXT,
                    parent_key TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
                    UNIQUE(project_id, stable_key)
                );
                CREATE TABLE IF NOT EXISTS ownership (
                    project_id TEXT NOT NULL REFERENCES projects(project_id), path TEXT NOT NULL,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id), owner TEXT NOT NULL,
                    operation_id TEXT NOT NULL, acquired_at INTEGER NOT NULL,
                    PRIMARY KEY(project_id, path)
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    attempt_no INTEGER NOT NULL, actor TEXT NOT NULL, role TEXT NOT NULL,
                    spec_revision INTEGER NOT NULL, changed_files_json TEXT NOT NULL,
                    checks_json TEXT NOT NULL, summary TEXT NOT NULL, state TEXT NOT NULL,
                    created_at INTEGER NOT NULL, UNIQUE(task_id, attempt_no)
                );
                CREATE TABLE IF NOT EXISTS attempt_context (
                    attempt_id TEXT PRIMARY KEY REFERENCES attempts(attempt_id),
                    engineer_ids_json TEXT NOT NULL, content_fingerprint TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS review_verdicts (
                    attempt_id TEXT PRIMARY KEY REFERENCES attempts(attempt_id),
                    verdict TEXT NOT NULL, rationale TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS context_immutable_update
                    BEFORE UPDATE ON attempt_context BEGIN SELECT RAISE(ABORT, 'attempt context is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS context_immutable_delete
                    BEFORE DELETE ON attempt_context BEGIN SELECT RAISE(ABORT, 'attempt context is immutable'); END;
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
                    criterion_id TEXT NOT NULL, kind TEXT NOT NULL, command TEXT NOT NULL,
                    cwd TEXT NOT NULL, exit_status INTEGER NOT NULL, output TEXT NOT NULL,
                    content_fingerprint TEXT NOT NULL, created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                    operation_id TEXT NOT NULL UNIQUE, event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS leases (
                    project_id TEXT PRIMARY KEY REFERENCES projects(project_id), holder TEXT NOT NULL,
                    expires_at INTEGER NOT NULL, acquired_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS dispatches (
                    operation_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                    task_id TEXT NOT NULL REFERENCES tasks(task_id), stable_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL, route_json TEXT NOT NULL, state TEXT NOT NULL,
                    native_task_id TEXT, effective_route_json TEXT NOT NULL DEFAULT '{}',
                    created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recovery_events (
                    event_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                    task_id TEXT NOT NULL REFERENCES tasks(task_id), failure_class TEXT NOT NULL,
                    phase TEXT NOT NULL, code TEXT NOT NULL, state TEXT NOT NULL,
                    route_identity TEXT NOT NULL, decision_json TEXT NOT NULL, created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_budgets (
                    task_id TEXT PRIMARY KEY REFERENCES tasks(task_id), repair_cycles INTEGER NOT NULL DEFAULT 0,
                    provider_recoveries INTEGER NOT NULL DEFAULT 0, native_launches INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS route_breakers (
                    route_identity TEXT PRIMARY KEY, failure_count INTEGER NOT NULL DEFAULT 0,
                    opened_until INTEGER NOT NULL DEFAULT 0, last_failure_at INTEGER NOT NULL,
                    state TEXT NOT NULL DEFAULT 'closed', half_open_claimed INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS worker_reservations (
                    operation_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                    task_id TEXT NOT NULL REFERENCES tasks(task_id), holder TEXT NOT NULL,
                    state TEXT NOT NULL, reserved_seconds INTEGER NOT NULL,
                    reserved_at INTEGER NOT NULL, released_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS runtime_reservations (
                    operation_id TEXT PRIMARY KEY REFERENCES worker_reservations(operation_id),
                    project_id TEXT NOT NULL REFERENCES projects(project_id), task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    reserved_seconds INTEGER NOT NULL, actual_seconds INTEGER NOT NULL DEFAULT 0,
                    state TEXT NOT NULL, started_at INTEGER NOT NULL, completed_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS limit_blockers (
                    blocker_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                    task_id TEXT REFERENCES tasks(task_id), operation_id TEXT NOT NULL,
                    limit_name TEXT NOT NULL, usage INTEGER NOT NULL, cap INTEGER NOT NULL,
                    unblock_condition TEXT NOT NULL, created_at INTEGER NOT NULL, resolved_at INTEGER
                );
                CREATE TRIGGER IF NOT EXISTS attempts_immutable_update
                    BEFORE UPDATE ON attempts BEGIN SELECT RAISE(ABORT, 'attempts are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS attempts_immutable_delete
                    BEFORE DELETE ON attempts BEGIN SELECT RAISE(ABORT, 'attempts are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS evidence_immutable_update
                    BEFORE UPDATE ON evidence BEGIN SELECT RAISE(ABORT, 'evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS evidence_immutable_delete
                    BEFORE DELETE ON evidence BEGIN SELECT RAISE(ABORT, 'evidence is immutable'); END;
                """
            )
            columns = {row["name"] for row in db.execute("PRAGMA table_info(dispatches)")}
            if "effective_route_json" not in columns:
                db.execute("ALTER TABLE dispatches ADD COLUMN effective_route_json TEXT NOT NULL DEFAULT '{}'")
            breaker_columns = {row["name"] for row in db.execute("PRAGMA table_info(route_breakers)")}
            if "state" not in breaker_columns:
                db.execute("ALTER TABLE route_breakers ADD COLUMN state TEXT NOT NULL DEFAULT 'closed'")
            if "half_open_claimed" not in breaker_columns:
                db.execute("ALTER TABLE route_breakers ADD COLUMN half_open_claimed INTEGER NOT NULL DEFAULT 0")
            if version < 6:
                self._migrate_request_associations(db)
            db.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))

    def _migrate_request_associations(self, db) -> None:
        for project in db.execute('SELECT * FROM projects').fetchall():
            root = project['root']
            suffix = re.search(r'#closed-' + re.escape(project['project_id']) + r'-\d+$', root)
            if suffix:
                if project['stage'] != 'closed':
                    raise SDDError('ambiguous archived request; restore/repair the v5 ledger before migration')
                root = root[:suffix.start()]
            root = str(Path(root).resolve())
            spec = db.execute('SELECT slug FROM specs WHERE project_id = ? ORDER BY revision DESC LIMIT 1', (project['project_id'],)).fetchone()
            if not spec:
                raise SDDError('request has no specification; repair before migration')
            spec_path = f"docs/sdd/features/{spec['slug']}/spec.md"
            db.execute('INSERT INTO request_repositories VALUES(?,?,?)', (project['project_id'], root, spec_path))
            if project['stage'] not in {'closed', 'abandoned'}:
                if db.execute('SELECT 1 FROM active_requests WHERE root = ?', (root,)).fetchone():
                    raise SDDError('multiple active requests resolve to the same repository; repair before migration')
                db.execute('INSERT INTO active_requests VALUES(?,?)', (root, project['project_id']))

    def append_event(self, project_id: str, event_type: str, payload: Mapping[str, Any], operation_id: str | None = None) -> bool:
        operation_id = operation_id or str(uuid.uuid4())
        with self._connect() as db:
            try:
                db.execute(
                    "INSERT INTO events(event_id, project_id, operation_id, event_type, payload_json, created_at) VALUES(?,?,?,?,?,?)",
                    (str(uuid.uuid4()), project_id, operation_id, event_type, json_text(payload), utc_now()),
                )
            except sqlite3.IntegrityError:
                return False
        self.export_jsonl()
        return True

    def init_project(self, request: str, mode: str, slug: str, board_slug: str, criteria: list[dict[str, Any]], task_specs: list[dict[str, Any]], limits: Mapping[str, int] | None = None) -> dict[str, Any]:
        root = str(self.paths.root.resolve())
        project_id = uuid.uuid4().hex[:16]
        now = utc_now()
        selected_limits = {**DEFAULT_LIMITS, **(limits or {})}
        spec_content = {"request": request, "mode": mode, "criteria": criteria, "tasks": task_specs}
        already_initialized = False
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute("SELECT project_id FROM active_requests WHERE root = ?", (root,)).fetchone()
            if existing:
                project_id = existing['project_id']
                project = db.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
                current = db.execute("SELECT request, mode, content_json FROM specs WHERE project_id = ? ORDER BY revision DESC LIMIT 1", (project_id,)).fetchone()
                if current and (current["request"] != request or current["mode"] != mode):
                    raise SDDError("repository already has a different active SDD request; close it after acceptance before starting another project")
                if current and current["content_json"] != json_text(spec_content):
                    raise SDDError("existing specification differs; explicit revision required before changing task policy")
                if limits is not None and json.loads(project['limits_json']) != selected_limits:
                    raise SDDError('existing limits differ; explicit revision required before changing limits')
                already_initialized = True
            if not already_initialized:
                board_slug = f'{board_slug[:40]}-{project_id}'
                db.execute(
                    "INSERT INTO projects(project_id, root, board_slug, stage, paused, limits_json, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
                    # Retain the legacy UNIQUE root column as an immutable
                    # storage key; request_repositories owns canonical roots.
                    (project_id, f'request:{project_id}', board_slug, "planned", 0, json_text(selected_limits), now, now),
                )
                db.execute('INSERT INTO request_repositories VALUES(?,?,?)', (project_id, root, f'docs/sdd/features/{slug}-{project_id}/spec.md'))
                db.execute('INSERT INTO active_requests VALUES(?,?)', (root, project_id))
                db.execute(
                    "INSERT INTO specs(spec_id, project_id, slug, revision, mode, request, content_json, created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()), project_id, slug, 1, mode, request, json_text(spec_content), now),
                )
                for index, task in enumerate(task_specs, start=1):
                    db.execute(
                        "INSERT INTO tasks(task_id, project_id, stable_key, title, role, kind, status, spec_revision, native_task_id, parent_key, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (f"{project_id}-T{index:03d}", project_id, task["stable_key"], task["title"], task["role"], task["kind"], "planned", 1, None, task.get("parent_key"), now, now),
                    )
                db.execute('INSERT INTO events VALUES(?,?,?,?,?,?)', (str(uuid.uuid4()), project_id, f'{project_id}:initialized', 'project_initialized', json_text({'mode': mode, 'board_slug': board_slug, 'limits': selected_limits}), now))
        self.export_jsonl()
        return {**(self.project(project_id) or {}), 'replayed': already_initialized}

    def project(self, project_id: str | None = None) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM projects WHERE project_id = ?", (project_id or self.project_id(),)).fetchone()
            if not row:
                return None
            result = dict(row)
            association = db.execute('SELECT root, spec_path FROM request_repositories WHERE project_id = ?', (row['project_id'],)).fetchone()
            if association:
                result.update(dict(association))
            result["limits"] = json.loads(result.pop("limits_json"))
            result["paused"] = bool(result["paused"])
            return result

    def project_id(self) -> str | None:
        root = str(self.paths.root.resolve())
        with self._connect() as db:
            row = db.execute("SELECT project_id FROM active_requests WHERE root = ?", (root,)).fetchone()
            if not row:
                # Preserve status/close replay for the most recently terminal
                # request until the next active request is initialized.
                row = db.execute('SELECT p.project_id FROM projects p JOIN request_repositories r ON r.project_id = p.project_id WHERE r.root = ? ORDER BY p.rowid DESC LIMIT 1', (root,)).fetchone()
            return row[0] if row else None

    def set_stage(self, stage: str, paused: bool | None = None) -> None:
        project_id = self.project_id()
        if not project_id:
            raise SDDError("project is not initialized; run /sdd plan or /sdd build first")
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT stage FROM projects WHERE project_id = ?', (project_id,)).fetchone()[0] in {'closed', 'abandoned'}:
                raise SDDError('terminal requests cannot change stage')
            if paused is None:
                db.execute("UPDATE projects SET stage = ?, updated_at = ? WHERE project_id = ?", (stage, utc_now(), project_id))
            else:
                db.execute("UPDATE projects SET stage = ?, paused = ?, updated_at = ? WHERE project_id = ?", (stage, int(paused), utc_now(), project_id))

    def close_project(self) -> dict[str, Any]:
        project_id = self.project_id()
        if not project_id:
            raise SDDError("project is not initialized")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            project = db.execute("SELECT stage, paused FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            if project["stage"] == "closed":
                return {"closed": True, "project_id": project_id, "idempotent": True}
            if project["paused"] or project["stage"] != "accepted":
                raise SDDError("only an unpaused accepted project can be closed")
            active = db.execute("SELECT COUNT(*) FROM worker_reservations WHERE project_id = ? AND state IN ('reserved', 'running', 'ambiguous')", (project_id,)).fetchone()[0]
            if active:
                raise SDDError("cannot close while worker reservations are active")
            db.execute("UPDATE projects SET stage = 'closed', updated_at = ? WHERE project_id = ?", (utc_now(), project_id))
            db.execute('DELETE FROM active_requests WHERE project_id = ?', (project_id,))
            db.execute('INSERT INTO events VALUES(?,?,?,?,?,?)', (str(uuid.uuid4()), project_id, f'{project_id}:closed', 'project_closed', json_text({'stage': 'accepted'}), utc_now()))
        self.export_jsonl()
        return {"closed": True, "project_id": project_id, "idempotent": False}

    def tasks(self) -> list[dict[str, Any]]:
        project_id = self.project_id()
        if not project_id:
            return []
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM tasks WHERE project_id = ? ORDER BY stable_key", (project_id,))]

    def task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            return dict(row) if row else None

    def set_native_task_id(self, task_id: str, native_task_id: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE tasks SET native_task_id = ?, status = 'queued', updated_at = ? WHERE task_id = ?", (native_task_id, utc_now(), task_id))

    def set_task_status(self, task_id: str, status: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?", (status, utc_now(), task_id))

    def admit_capacity(self, task_id: str, operation_id: str, holder: str, runtime_seconds: int) -> dict[str, Any]:
        """Atomically reserve worker and runtime capacity before native dispatch."""
        task = self.task(task_id)
        if not task:
            raise SDDError(f"unknown task: {task_id}")
        project_id = task["project_id"]
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM worker_reservations WHERE operation_id = ?", (operation_id,)).fetchone()
            if existing:
                if (existing['task_id'], existing['holder'], existing['reserved_seconds']) != (task_id, holder, runtime_seconds):
                    raise SDDError('capacity operation ID was already used with different inputs')
                return {**dict(existing), "allowed": existing["state"] in {"reserved", "running"}, "replayed": True,
                        'blocked': 'reconcile_reservation', 'unblock_condition': 'reconcile the existing capacity operation'}
            project = db.execute("SELECT stage, paused, limits_json FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            if project['stage'] in {'closed', 'abandoned'}:
                raise SDDError('terminal requests cannot reserve capacity')
            limits = json.loads(project["limits_json"])
            max_workers = int(limits.get("max_workers", DEFAULT_LIMITS["max_workers"]))
            max_runtime = int(limits.get("max_runtime_seconds", DEFAULT_LIMITS["max_runtime_seconds"]))
            max_total_runtime = int(limits.get("max_total_runtime_seconds", DEFAULT_LIMITS["max_total_runtime_seconds"]))
            active = db.execute("SELECT COUNT(*) FROM worker_reservations WHERE project_id = ? AND state IN ('reserved', 'running', 'ambiguous')", (project_id,)).fetchone()[0]
            exposure = "CASE WHEN state IN ('reserved', 'running', 'ambiguous') THEN MAX(reserved_seconds, actual_seconds) ELSE actual_seconds END"
            total_runtime = db.execute(f"SELECT COALESCE(SUM({exposure}), 0) FROM runtime_reservations WHERE project_id = ?", (project_id,)).fetchone()[0]
            task_runtime = db.execute(f"SELECT COALESCE(SUM({exposure}), 0) FROM runtime_reservations WHERE task_id = ?", (task_id,)).fetchone()[0]

            def blocked(limit_name: str, usage: int, cap: int, condition: str) -> dict[str, Any]:
                blocker_id = str(uuid.uuid4())
                db.execute("INSERT INTO limit_blockers(blocker_id, project_id, task_id, operation_id, limit_name, usage, cap, unblock_condition, created_at, resolved_at) VALUES(?,?,?,?,?,?,?,?,?,NULL)", (blocker_id, project_id, task_id, operation_id, limit_name, usage, cap, condition, now))
                return {"allowed": False, "blocked": limit_name, "usage": usage, "cap": cap, "unblock_condition": condition, "blocker_id": blocker_id, "replayed": False}

            if project["paused"]:
                return blocked("paused", 1, 0, "resume the project")
            if runtime_seconds <= 0 or task_runtime + runtime_seconds > max_runtime:
                return blocked("task_runtime", task_runtime + runtime_seconds, max_runtime, "choose a runtime within the remaining task budget")
            if active >= max_workers:
                return blocked("max_workers", active, max_workers, "complete or release an active worker reservation")
            if total_runtime + runtime_seconds > max_total_runtime:
                return blocked("total_runtime", total_runtime + runtime_seconds, max_total_runtime, "reconcile unused reservations or explicitly revise the total runtime cap; consumed time is retained")
            db.execute("INSERT INTO worker_reservations(operation_id, project_id, task_id, holder, state, reserved_seconds, reserved_at, released_at) VALUES(?,?,?,?,?,?,?,NULL)", (operation_id, project_id, task_id, holder, "reserved", runtime_seconds, now))
            db.execute("INSERT INTO runtime_reservations(operation_id, project_id, task_id, reserved_seconds, actual_seconds, state, started_at, completed_at) VALUES(?,?,?,?,?,?,?,NULL)", (operation_id, project_id, task_id, runtime_seconds, 0, "reserved", now))
            db.execute('UPDATE limit_blockers SET resolved_at = ? WHERE project_id = ? AND operation_id = ? AND resolved_at IS NULL', (now, project_id, operation_id))
            return {"allowed": True, "operation_id": operation_id, "task_id": task_id, "reserved_seconds": runtime_seconds, "replayed": False}

    def complete_capacity(self, operation_id: str, actual_seconds: int, state: str = "completed") -> dict[str, Any]:
        if state not in {"completed", "failed", "released", "ambiguous"}:
            raise SDDError(f"invalid capacity completion state: {state}")
        if not isinstance(actual_seconds, int) or isinstance(actual_seconds, bool) or actual_seconds < 0:
            raise SDDError('actual runtime must be a nonnegative integer')
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            reservation = db.execute("SELECT * FROM worker_reservations WHERE operation_id = ?", (operation_id,)).fetchone()
            runtime = db.execute("SELECT * FROM runtime_reservations WHERE operation_id = ?", (operation_id,)).fetchone()
            if not reservation or not runtime:
                raise SDDError("unknown capacity reservation")
            if reservation["state"] not in {"reserved", "running", "ambiguous"}:
                if reservation['state'] != state or runtime['actual_seconds'] != actual_seconds:
                    raise SDDError('capacity completion was already recorded with different inputs')
                return {"operation_id": operation_id, "state": reservation["state"], "idempotent": True}
            if actual_seconds < runtime['actual_seconds']:
                raise SDDError('actual runtime cannot decrease during reconciliation')
            now = utc_now()
            terminal_at = None if state == 'ambiguous' else now
            db.execute("UPDATE worker_reservations SET state = ?, released_at = ? WHERE operation_id = ?", (state, terminal_at, operation_id))
            db.execute("UPDATE runtime_reservations SET state = ?, actual_seconds = ?, completed_at = ? WHERE operation_id = ?", (state, actual_seconds, terminal_at, operation_id))
            # Completion does not prove every runtime blocker has been resolved.
            active = db.execute("SELECT COUNT(*) FROM worker_reservations WHERE project_id = ? AND state IN ('reserved', 'running', 'ambiguous')", (reservation['project_id'],)).fetchone()[0]
            limits = json.loads(db.execute('SELECT limits_json FROM projects WHERE project_id = ?', (reservation['project_id'],)).fetchone()[0])
            if active < int(limits.get('max_workers', DEFAULT_LIMITS['max_workers'])):
                db.execute("UPDATE limit_blockers SET resolved_at = ? WHERE project_id = ? AND resolved_at IS NULL AND limit_name = 'max_workers'", (now, reservation['project_id']))
            db.execute('INSERT INTO events VALUES(?,?,?,?,?,?)', (str(uuid.uuid4()), reservation['project_id'], str(uuid.uuid4()), 'capacity_reconciled', json_text({'operation_id': operation_id, 'state': state, 'actual_seconds': actual_seconds}), now))
        self.export_jsonl()
        return {"operation_id": operation_id, "state": state, "actual_seconds": actual_seconds, "idempotent": False}

    def reservation(self, operation_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM worker_reservations WHERE operation_id = ?", (operation_id,)).fetchone()
            return dict(row) if row else None

    def capacity(self) -> list[dict[str, Any]]:
        project_id = self.project_id()
        if not project_id:
            return []
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT w.*, r.actual_seconds, r.state AS runtime_state FROM worker_reservations w JOIN runtime_reservations r ON r.operation_id = w.operation_id WHERE w.project_id = ? ORDER BY w.reserved_at", (project_id,))]

    def blockers(self) -> list[dict[str, Any]]:
        project_id = self.project_id()
        if not project_id:
            return []
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM limit_blockers WHERE project_id = ? AND resolved_at IS NULL ORDER BY created_at DESC", (project_id,))]

    def dispatch_intent(self, task_id: str, stable_key: str, operation_id: str, payload: Mapping[str, Any], route: Mapping[str, Any]) -> dict[str, Any]:
        task = self.task(task_id)
        if not task:
            raise SDDError(f"unknown task: {task_id}")
        project_id = task["project_id"]
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM dispatches WHERE operation_id = ?", (operation_id,)).fetchone()
            encoded_payload, encoded_route = json_text(payload), json_text(route)
            if existing:
                if existing["project_id"] != project_id or existing["payload_json"] != encoded_payload or existing["route_json"] != encoded_route:
                    raise SDDError("dispatch operation ID was already used with different inputs")
                result = dict(existing)
                result["replayed"] = True
                return result
            now = utc_now()
            db.execute(
                "INSERT INTO dispatches(operation_id, project_id, task_id, stable_key, payload_json, route_json, state, native_task_id, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (operation_id, project_id, task_id, stable_key, encoded_payload, encoded_route, "pending", None, now, now),
            )
            return {"operation_id": operation_id, "project_id": project_id, "task_id": task_id, "stable_key": stable_key, "state": "pending", "native_task_id": None, "replayed": False}

    def complete_dispatch(self, operation_id: str, native_task_id: str, effective_route: Mapping[str, Any] | None = None) -> None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM dispatches WHERE operation_id = ?", (operation_id,)).fetchone()
            if not row:
                raise SDDError("unknown dispatch operation")
            now = utc_now()
            db.execute("UPDATE dispatches SET state = 'completed', native_task_id = ?, effective_route_json = ?, updated_at = ? WHERE operation_id = ?", (native_task_id, json_text(effective_route or {}), now, operation_id))
            db.execute("INSERT OR IGNORE INTO task_budgets(task_id, updated_at) VALUES(?,?)", (row["task_id"], now))
            db.execute("UPDATE task_budgets SET native_launches = native_launches + 1, updated_at = ? WHERE task_id = ?", (now, row["task_id"]))
            if effective_route:
                identity = f"{effective_route.get('provider', '')}/{effective_route.get('model', '')}@{effective_route.get('endpoint') or 'default'}"
                db.execute("UPDATE route_breakers SET state = 'closed', opened_until = 0, half_open_claimed = 0 WHERE route_identity = ?", (identity,))

    def dispatches(self) -> list[dict[str, Any]]:
        project_id = self.project_id()
        if not project_id:
            return []
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM dispatches WHERE project_id = ? ORDER BY created_at", (project_id,))]

    def record_recovery(self, task_id: str, failure: Mapping[str, str], decision: Mapping[str, Any], route_identity: str, retry_after: int | None = None) -> dict[str, Any]:
        task = self.task(task_id)
        if not task:
            raise SDDError(f"unknown task: {task_id}")
        event_id = str(uuid.uuid4())
        with self._connect() as db:
            db.execute(
                "INSERT INTO recovery_events(event_id, project_id, task_id, failure_class, phase, code, state, route_identity, decision_json, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (event_id, task["project_id"], task_id, failure["class"], failure.get("phase", "dispatch"), failure.get("code", ""), decision["state"], route_identity, json_text(decision), utc_now()),
            )
            if failure["class"] == "provider_transient":
                now = utc_now()
                cooldown = max(0, int(retry_after if retry_after is not None else 60))
                db.execute("INSERT INTO route_breakers(route_identity, failure_count, opened_until, last_failure_at, state, half_open_claimed) VALUES(?,?,?,?,?,?) ON CONFLICT(route_identity) DO UPDATE SET failure_count = failure_count + 1, opened_until = excluded.opened_until, last_failure_at = excluded.last_failure_at, state = 'open', half_open_claimed = 0", (route_identity, 1, now + cooldown, now, "open", 0))
        return {"event_id": event_id, "task_id": task_id, "failure": dict(failure), "decision": dict(decision), "route_identity": route_identity}

    def recovery_events(self) -> list[dict[str, Any]]:
        project_id = self.project_id()
        if not project_id:
            return []
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM recovery_events WHERE project_id = ? ORDER BY created_at", (project_id,))]

    def recovery_admission(self, task_id: str, failure_class: str, route_identity: str, actionable_change: str | None) -> dict[str, Any]:
        """Reserve a repair/provider budget only when every durable gate passes."""
        task = self.task(task_id)
        if not task:
            raise SDDError(f"unknown task: {task_id}")
        project_id = task["project_id"]
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            project = db.execute("SELECT paused, limits_json FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            if project["paused"]:
                return {"allowed": False, "state": "blocked", "reason": "project is paused"}
            breaker = db.execute("SELECT * FROM route_breakers WHERE route_identity = ?", (route_identity,)).fetchone()
            if failure_class == "provider_transient" and breaker and breaker["opened_until"] > now:
                return {"allowed": False, "state": "waiting_provider", "reason": "route cooldown is active", "retry_at": breaker["opened_until"]}
            if failure_class == "provider_transient" and breaker and breaker["state"] in {"open", "half_open"}:
                if breaker["half_open_claimed"]:
                    return {"allowed": False, "state": "waiting_provider", "reason": "half-open provider probe already claimed"}
                db.execute("UPDATE route_breakers SET state = 'half_open', half_open_claimed = 1 WHERE route_identity = ?", (route_identity,))
            if not actionable_change:
                return {"allowed": False, "state": "waiting_provider" if failure_class == "provider_transient" else "blocked", "reason": "an actionable recovery change is required"}
            limits = json.loads(project["limits_json"])
            db.execute("INSERT OR IGNORE INTO task_budgets(task_id, updated_at) VALUES(?,?)", (task_id, now))
            budget = db.execute("SELECT * FROM task_budgets WHERE task_id = ?", (task_id,)).fetchone()
            if failure_class == "task_defect":
                if budget["repair_cycles"] >= int(limits.get("max_repairs", DEFAULT_LIMITS["max_repairs"])):
                    return {"allowed": False, "state": "blocked", "reason": "repair budget exhausted"}
                column = "repair_cycles"
            elif failure_class == "provider_transient":
                if budget["provider_recoveries"] >= int(limits.get("max_provider_recoveries", DEFAULT_LIMITS["max_provider_recoveries"])):
                    return {"allowed": False, "state": "blocked", "reason": "provider recovery budget exhausted"}
                column = "provider_recoveries"
            else:
                return {"allowed": False, "state": "blocked", "reason": f"failure class {failure_class} is not launch-admissible"}
            db.execute(f"UPDATE task_budgets SET {column} = {column} + 1, updated_at = ? WHERE task_id = ?", (now, task_id))
            return {"allowed": True, "state": "dispatch_pending", "budget": column}

    def budgets(self) -> list[dict[str, Any]]:
        project_id = self.project_id()
        if not project_id:
            return []
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT b.* FROM task_budgets b JOIN tasks t ON t.task_id = b.task_id WHERE t.project_id = ? ORDER BY b.task_id", (project_id,))]

    def breakers(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM route_breakers ORDER BY route_identity")]

    def acquire_ownership(self, task_id: str, owner: str, files: Sequence[str], operation_id: str) -> list[str]:
        task = self.task(task_id)
        if not task:
            raise SDDError(f"unknown task: {task_id}")
        project_id = task["project_id"]
        normalized = sorted({safe_relative(self.paths.root, item) for item in files})
        payload = {"task_id": task_id, "owner": owner, "files": normalized}
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT project_id, event_type, payload_json FROM events WHERE operation_id = ?", (operation_id,)).fetchone()
            if previous:
                if previous["project_id"] != project_id or previous["event_type"] != "ownership_acquired" or previous["payload_json"] != json_text(payload):
                    raise SDDError("operation ID was already used with different inputs")
                return normalized
            project = db.execute("SELECT paused FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            if project["paused"]:
                raise SDDError("project is paused")
            existing = db.execute("SELECT path, task_id, owner FROM ownership WHERE project_id = ?", (project_id,)).fetchall()
            for path in normalized:
                for held in existing:
                    if held["task_id"] != task_id and (path == held["path"] or path.startswith(held["path"] + "/") or held["path"].startswith(path + "/")):
                        raise SDDError(f"file ownership conflict for {path}: held by {held['task_id']} ({held['owner']})")
            now = utc_now()
            for path in normalized:
                db.execute(
                    "INSERT OR REPLACE INTO ownership(project_id, path, task_id, owner, operation_id, acquired_at) VALUES(?,?,?,?,?,?)",
                    (project_id, path, task_id, owner, operation_id, now),
                )
            db.execute("INSERT INTO events VALUES(?,?,?,?,?,?)", (str(uuid.uuid4()), project_id, operation_id, "ownership_acquired", json_text(payload), now))
            db.execute("UPDATE tasks SET status = 'running', updated_at = ? WHERE task_id = ?", (now, task_id))
        self.export_jsonl()
        return normalized

    def release_ownership(self, task_id: str) -> None:
        task = self.task(task_id)
        if not task:
            raise SDDError(f"unknown task: {task_id}")
        with self._connect() as db:
            db.execute("DELETE FROM ownership WHERE project_id = ? AND task_id = ?", (task["project_id"], task_id))

    @staticmethod
    def _current_attempts(db, project_id: str) -> list[dict[str, Any]]:
        return [dict(row) for row in db.execute(
            "SELECT a.* FROM attempts a JOIN tasks t ON t.task_id = a.task_id "
            "WHERE t.project_id = ? AND a.attempt_no = "
            "(SELECT MAX(b.attempt_no) FROM attempts b WHERE b.task_id = a.task_id) "
            "ORDER BY a.task_id", (project_id,))]

    def create_attempt(self, task_id: str, actor: str, role: str, spec_revision: int, changed_files: Sequence[str], checks: Sequence[str], summary: str, state: str = "submitted", attempt_id: str | None = None, verdict: str | None = None) -> dict[str, Any]:
        attempt_id = attempt_id or str(uuid.uuid4())
        normalized = sorted({safe_relative(self.paths.root, path) for path in changed_files})
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            task = db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not task:
                raise SDDError(f"unknown task: {task_id}")
            revision = db.execute("SELECT MAX(revision) FROM specs WHERE project_id = ?", (task["project_id"],)).fetchone()[0]
            if spec_revision != revision or spec_revision != task["spec_revision"]:
                raise SDDError(f"stale specification revision {spec_revision}; current is {revision}")
            if role != task["role"]:
                raise SDDError("submission role does not match task")
            current = self._current_attempts(db, task["project_id"])
            engineers = sorted(a["attempt_id"] for a in current if a["role"] == "engineer")
            attempt_no = db.execute("SELECT COALESCE(MAX(attempt_no), 0) + 1 FROM attempts WHERE task_id = ?", (task_id,)).fetchone()[0]
            db.execute(
                "INSERT INTO attempts(attempt_id, task_id, attempt_no, actor, role, spec_revision, changed_files_json, checks_json, summary, state, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (attempt_id, task_id, attempt_no, actor, role, spec_revision, json_text(normalized), json_text(list(checks)), summary, state, utc_now()),
            )
            db.execute("INSERT INTO attempt_context VALUES(?,?,?)", (attempt_id, json_text(engineers), file_fingerprint(self.paths.root, normalized)))
            if role == "reviewer":
                if verdict not in {"approve", "request_changes"}:
                    raise SDDError("review verdict must be approve or request_changes")
                db.execute("INSERT INTO review_verdicts(attempt_id, verdict, rationale, created_at) VALUES(?,?,?,?)", (attempt_id, verdict, summary, utc_now()))
            db.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?", ("review" if role == "engineer" else "submitted", utc_now(), task_id))
            db.execute("UPDATE projects SET stage = CASE WHEN paused = 1 THEN 'paused' ELSE 'review' END, updated_at = ? WHERE project_id = ?", (utc_now(), task["project_id"]))
        return {"attempt_id": attempt_id, "attempt_no": attempt_no, "task_id": task_id}

    def verification_scope(self, attempt_id: str, criterion_id: str, changed_files: Sequence[str]) -> list[str]:
        with self._connect() as db:
            attempt = db.execute("SELECT a.*, t.project_id FROM attempts a JOIN tasks t ON t.task_id = a.task_id WHERE attempt_id = ?", (attempt_id,)).fetchone()
            if not attempt:
                raise SDDError(f"unknown attempt: {attempt_id}")
            current = self._current_attempts(db, attempt["project_id"])
            if attempt_id not in {a["attempt_id"] for a in current}:
                raise SDDError("cannot verify a superseded attempt")
            spec = db.execute("SELECT revision, content_json FROM specs WHERE project_id = ? ORDER BY revision DESC LIMIT 1", (attempt["project_id"],)).fetchone()
            if attempt["spec_revision"] != spec["revision"]:
                raise SDDError("cannot verify an obsolete specification")
            if criterion_id not in {c["id"] for c in json.loads(spec["content_json"])["criteria"]}:
                raise SDDError(f"unknown criterion: {criterion_id}")
            context = db.execute("SELECT * FROM attempt_context WHERE attempt_id = ?", (attempt_id,)).fetchone()
            engineers = sorted(a["attempt_id"] for a in current if a["role"] == "engineer")
            if not context or (attempt["role"] != "engineer" and json.loads(context["engineer_ids_json"]) != engineers):
                raise SDDError("attempt is not bound to the current implementation; resubmit")
        scope = json.loads(attempt["changed_files_json"])
        supplied = sorted({safe_relative(self.paths.root, path) for path in changed_files})
        if supplied != scope:
            raise SDDError("verification file scope must match the submitted attempt")
        if context["content_fingerprint"] != file_fingerprint(self.paths.root, scope):
            raise SDDError("submitted files changed; submit a new attempt before verification")
        return scope

    def add_evidence(self, attempt_id: str, criterion_id: str, kind: str, command: str, cwd: str, exit_status: int, output: str, content_fingerprint: str) -> str:
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM attempts WHERE attempt_id = ?", (attempt_id,)).fetchone():
                raise SDDError(f"unknown attempt: {attempt_id}")
            evidence_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO evidence(evidence_id, attempt_id, criterion_id, kind, command, cwd, exit_status, output, content_fingerprint, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (evidence_id, attempt_id, criterion_id, kind, command, cwd, exit_status, output[-20000:], content_fingerprint, utc_now()),
            )
        return evidence_id

    def accept(self, task_id: str, required_criteria: Sequence[Mapping[str, Any]], root: Path) -> dict[str, Any]:
        if not self.task(task_id):
            raise SDDError(f"unknown task: {task_id}")
        # Task acceptance must not bypass the project-wide engineer/reviewer contract.
        result = self.accept_project(required_criteria, root)
        if result["accepted"]:
            self.set_task_status(task_id, "accepted")
        return {**result, "task_id": task_id}

    def accept_project(self, required_criteria: Sequence[Mapping[str, Any]], root: Path) -> dict[str, Any]:
        project_id = self.project_id()
        if not project_id:
            raise SDDError("project is not initialized")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            spec = db.execute("SELECT revision, content_json FROM specs WHERE project_id = ? ORDER BY revision DESC LIMIT 1", (project_id,)).fetchone()
            # The stored specification is authoritative; callers cannot omit criteria.
            required = {c["id"] for c in json.loads(spec["content_json"])["criteria"] if c.get("required", True)}
            attempts = self._current_attempts(db, project_id)
            contexts = {row["attempt_id"]: dict(row) for row in db.execute("SELECT * FROM attempt_context")}
            engineers = [a for a in attempts if a["role"] == "engineer"]
            engineer_ids = sorted(a["attempt_id"] for a in engineers)
            engineer_actors = {a["actor"] for a in engineers}
            engineer_files = {path for a in engineers for path in json.loads(a["changed_files_json"])}
            reasons: list[str] = []
            for task in db.execute("SELECT task_id FROM tasks WHERE project_id = ? AND role = 'engineer'", (project_id,)):
                if task["task_id"] not in {a["task_id"] for a in engineers}:
                    reasons.append("engineer submission is missing")
            for attempt in engineers:
                if not json.loads(attempt["changed_files_json"]):
                    reasons.append(f"engineer submission {attempt['attempt_id']} has empty implementation scope")
                if not json.loads(attempt["checks_json"]):
                    reasons.append(f"engineer submission {attempt['attempt_id']} declares no required checks")
            eligible = {}
            for attempt in attempts:
                context = contexts.get(attempt["attempt_id"])
                if attempt["spec_revision"] != spec["revision"] or not context:
                    reasons.append(f"attempt {attempt['attempt_id']} is obsolete or lacks submission context; resubmit")
                    continue
                if attempt["role"] != "engineer" and json.loads(context["engineer_ids_json"]) != engineer_ids:
                    reasons.append(f"attempt {attempt['attempt_id']} targets a superseded implementation")
                    continue
                if context["content_fingerprint"] != file_fingerprint(root, json.loads(attempt["changed_files_json"])):
                    reasons.append(f"submission is stale for {attempt['task_id']}; changed files no longer match")
                    continue
                if attempt["state"] not in {"submitted", "accepted"}:
                    reasons.append(f"submission is not successful for {attempt['task_id']}")
                    continue
                eligible[attempt["attempt_id"]] = attempt
            reviewers = [a for a in eligible.values() if a["role"] == "reviewer" and a["actor"] not in engineer_actors and engineer_files <= set(json.loads(a["changed_files_json"]))]
            if not reviewers:
                reasons.append("independent reviewer submission is missing")
            for reviewer in reviewers:
                verdict = db.execute("SELECT verdict FROM review_verdicts WHERE attempt_id = ?", (reviewer["attempt_id"],)).fetchone()
                if not verdict or verdict["verdict"] != "approve":
                    reasons.append(f"reviewer verdict requests changes for {reviewer['task_id']}")
            evidence = [dict(row) for row in db.execute(
                "SELECT e.* FROM evidence e JOIN attempts a ON a.attempt_id = e.attempt_id JOIN tasks t ON t.task_id = a.task_id WHERE t.project_id = ? ORDER BY e.rowid", (project_id,))]
            latest = {}
            for item in evidence:
                if item["attempt_id"] in eligible:
                    latest[(item["attempt_id"], item["criterion_id"], item["command"])] = item
            covered = set()
            passed_commands = set()
            for item in latest.values():
                attempt = eligible[item["attempt_id"]]
                if item["exit_status"] != 0:
                    reasons.append(f"verification failed for {item['criterion_id']} (exit {item['exit_status']})")
                elif item["content_fingerprint"] != file_fingerprint(root, json.loads(attempt["changed_files_json"])):
                    reasons.append(f"evidence is stale for {item['criterion_id']}")
                else:
                    covered.add(item["criterion_id"])
                    passed_commands.add((item["attempt_id"], item["command"]))
            reasons.extend(f"missing evidence for {c}" for c in sorted(required - covered))
            for attempt in eligible.values():
                for command in json.loads(attempt["checks_json"]):
                    if (attempt["attempt_id"], command) not in passed_commands:
                        reasons.append(f"missing passing required command for {attempt['task_id']}: {command}")
            accepted = not reasons
            db.execute("UPDATE projects SET stage = CASE WHEN paused = 1 THEN 'paused' ELSE ? END, updated_at = ? WHERE project_id = ?", ("accepted" if accepted else "review", utc_now(), project_id))
            if not accepted:
                db.execute("UPDATE tasks SET status = 'review' WHERE project_id = ? AND status = 'accepted'", (project_id,))
        return {"accepted": accepted, "project_id": project_id, "reasons": reasons, "criteria": sorted(required), "evidence_count": len(latest)}

    def status(self) -> dict[str, Any]:
        project = self.project()
        if not project:
            return {"initialized": False}
        tasks = self.tasks()
        counts: dict[str, int] = {}
        for task in tasks:
            counts[task["status"]] = counts.get(task["status"], 0) + 1
        with self._connect() as db:
            ownership = [dict(row) for row in db.execute("SELECT path, task_id, owner FROM ownership WHERE project_id = ? ORDER BY path", (project["project_id"],))]
            blockers = [dict(row) for row in db.execute("SELECT event_type, payload_json, created_at FROM events WHERE project_id = ? AND event_type IN ('blocked', 'recovery_warning') ORDER BY created_at DESC LIMIT 10", (project["project_id"],))]
        return {"initialized": True, "project": project, "task_counts": counts, "tasks": tasks, "ownership": ownership, "blockers": blockers}

    def acquire_lease(self, holder: str, ttl: int = 60) -> bool:
        project_id = self.project_id()
        if not project_id:
            raise SDDError("project is not initialized")
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT holder, expires_at FROM leases WHERE project_id = ?", (project_id,)).fetchone()
            if current and current["expires_at"] > now and current["holder"] != holder:
                return False
            db.execute("INSERT OR REPLACE INTO leases(project_id, holder, expires_at, acquired_at) VALUES(?,?,?,?)", (project_id, holder, now + ttl, now))
        return True

    def renew_lease(self, holder: str, ttl: int = 60) -> bool:
        project_id = self.project_id()
        if not project_id:
            raise SDDError("project is not initialized")
        with self._connect() as db:
            now = utc_now()
            changed = db.execute("UPDATE leases SET expires_at = ? WHERE project_id = ? AND holder = ? AND expires_at > ?", (now + ttl, project_id, holder, now)).rowcount
            return changed == 1

    def release_lease(self, holder: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM leases WHERE project_id = ? AND holder = ?", (self.project_id(), holder))

    def export_jsonl(self) -> Path:
        # Rebuild from the authoritative SQLite event log after interrupted exports.
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT * FROM events ORDER BY rowid").fetchall()
            temporary = self.paths.jsonl.with_suffix(".jsonl.tmp")
            with temporary.open("w", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json_text({"at": row["created_at"], "project_id": row["project_id"], "operation_id": row["operation_id"], "event_type": row["event_type"], "payload": json.loads(row["payload_json"])}) + "\n")
            temporary.replace(self.paths.jsonl)
        return self.paths.jsonl


class VerificationRunner:
    """Run explicit checks and persist their evidence; not an OS sandbox."""

    def __init__(self, ledger: Ledger, root: Path):
        self.ledger = ledger
        self.root = root

    def run(self, attempt_id: str, criterion_id: str, command: str, changed_files: Sequence[str], timeout: int = 300) -> dict[str, Any]:
        changed_files = self.ledger.verification_scope(attempt_id, criterion_id, changed_files)
        before = file_fingerprint(self.root, changed_files)
        argv = shlex.split(command)
        if not argv:
            raise SDDError("verification command cannot be empty")
        started = time.monotonic()
        try:
            completed = subprocess.run(argv, cwd=self.root, capture_output=True, text=True, timeout=timeout, check=False)
            status = completed.returncode
            output = (completed.stdout + "\n" + completed.stderr).strip()
        except subprocess.TimeoutExpired as exc:
            status = 124
            output = f"timed out after {timeout}s\n{exc.stdout or ''}\n{exc.stderr or ''}".strip()
        except OSError as exc:
            status = 127
            output = str(exc)
        fingerprint = file_fingerprint(self.root, changed_files)
        if fingerprint != before:
            status = status or 1
            output += "\nVerification changed submitted files; resubmit before acceptance."
        evidence_id = self.ledger.add_evidence(attempt_id, criterion_id, "command", command, str(self.root), status, output, fingerprint)
        return {"evidence_id": evidence_id, "criterion_id": criterion_id, "exit_status": status, "duration_ms": int((time.monotonic() - started) * 1000), "output": output, "fingerprint_before": before, "fingerprint_after": fingerprint}
