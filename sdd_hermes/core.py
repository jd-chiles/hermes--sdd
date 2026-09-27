"""Durable, repository-local state for Hermes SDD.

The ledger is intentionally independent from Hermes' Kanban database.  Hermes owns
worker lifecycle and board transitions; this package owns the evidence needed to
decide whether a local result is actually acceptable.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import sqlite3
import subprocess
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = 1
DEFAULT_LIMITS = {"max_workers": 3, "max_repairs": 2, "max_runtime_seconds": 3600}


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
        self.paths.prepare()
        self._init_database()

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
            db.executescript(
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
            db.execute("INSERT OR IGNORE INTO metadata(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))

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
        self._append_jsonl({"project_id": project_id, "operation_id": operation_id, "event_type": event_type, "payload": payload})
        return True

    def _append_jsonl(self, event: Mapping[str, Any]) -> None:
        with self.paths.jsonl.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"at": utc_now(), **event}, sort_keys=True) + "\n")

    def init_project(self, request: str, mode: str, slug: str, board_slug: str, criteria: list[dict[str, Any]], task_specs: list[dict[str, Any]], limits: Mapping[str, int] | None = None) -> dict[str, Any]:
        root = str(self.paths.root)
        project_id = hashlib.sha256(root.encode("utf-8")).hexdigest()[:16]
        now = utc_now()
        selected_limits = {**DEFAULT_LIMITS, **(limits or {})}
        spec_content = {"request": request, "mode": mode, "criteria": criteria, "tasks": task_specs}
        already_initialized = False
        with self._connect() as db:
            existing = db.execute("SELECT project_id FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            if existing:
                current = db.execute("SELECT request, mode FROM specs WHERE project_id = ? ORDER BY revision DESC LIMIT 1", (project_id,)).fetchone()
                if current and (current["request"] != request or current["mode"] != mode):
                    raise SDDError("repository already has a different active SDD request; finish or recover it before starting another project")
                already_initialized = True
            else:
                db.execute(
                    "INSERT INTO projects(project_id, root, board_slug, stage, paused, limits_json, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
                    (project_id, root, board_slug, "planned", 0, json_text(selected_limits), now, now),
                )
                db.execute(
                    "INSERT INTO specs(spec_id, project_id, slug, revision, mode, request, content_json, created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()), project_id, slug, 1, mode, request, json_text(spec_content), now),
                )
                for index, task in enumerate(task_specs, start=1):
                    db.execute(
                        "INSERT INTO tasks(task_id, project_id, stable_key, title, role, kind, status, spec_revision, native_task_id, parent_key, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (f"{project_id}-T{index:03d}", project_id, task["stable_key"], task["title"], task["role"], task["kind"], "planned", 1, None, task.get("parent_key"), now, now),
                    )
        if already_initialized:
            return self.project(project_id) or {}
        self.append_event(project_id, "project_initialized", {"mode": mode, "board_slug": board_slug, "limits": selected_limits})
        return self.project(project_id) or {}

    def project(self, project_id: str | None = None) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM projects WHERE project_id = ?", (project_id or self.project_id(),)).fetchone()
            if not row:
                return None
            result = dict(row)
            result["limits"] = json.loads(result.pop("limits_json"))
            result["paused"] = bool(result["paused"])
            return result

    def project_id(self) -> str | None:
        root = str(self.paths.root)
        with self._connect() as db:
            row = db.execute("SELECT project_id FROM projects WHERE root = ?", (root,)).fetchone()
            return row[0] if row else None

    def set_stage(self, stage: str, paused: bool | None = None) -> None:
        project_id = self.project_id()
        if not project_id:
            raise SDDError("project is not initialized; run /sdd plan or /sdd build first")
        with self._connect() as db:
            if paused is None:
                db.execute("UPDATE projects SET stage = ?, updated_at = ? WHERE project_id = ?", (stage, utc_now(), project_id))
            else:
                db.execute("UPDATE projects SET stage = ?, paused = ?, updated_at = ? WHERE project_id = ?", (stage, int(paused), utc_now(), project_id))

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

    def acquire_ownership(self, task_id: str, owner: str, files: Sequence[str], operation_id: str) -> list[str]:
        task = self.task(task_id)
        if not task:
            raise SDDError(f"unknown task: {task_id}")
        project_id = task["project_id"]
        normalized = [safe_relative(self.paths.root, item) for item in files]
        with self._connect() as db:
            for path in normalized:
                existing = db.execute("SELECT task_id, owner FROM ownership WHERE project_id = ? AND path = ?", (project_id, path)).fetchone()
                if existing and existing["task_id"] != task_id:
                    raise SDDError(f"file ownership conflict for {path}: held by {existing['task_id']} ({existing['owner']})")
            now = utc_now()
            for path in normalized:
                db.execute(
                    "INSERT OR REPLACE INTO ownership(project_id, path, task_id, owner, operation_id, acquired_at) VALUES(?,?,?,?,?,?)",
                    (project_id, path, task_id, owner, operation_id, now),
                )
        self.append_event(project_id, "ownership_acquired", {"task_id": task_id, "owner": owner, "files": normalized}, operation_id)
        return normalized

    def release_ownership(self, task_id: str) -> None:
        task = self.task(task_id)
        if not task:
            raise SDDError(f"unknown task: {task_id}")
        with self._connect() as db:
            db.execute("DELETE FROM ownership WHERE project_id = ? AND task_id = ?", (task["project_id"], task_id))

    def create_attempt(self, task_id: str, actor: str, role: str, spec_revision: int, changed_files: Sequence[str], checks: Sequence[str], summary: str, state: str = "submitted", attempt_id: str | None = None) -> dict[str, Any]:
        task = self.task(task_id)
        if not task:
            raise SDDError(f"unknown task: {task_id}")
        if spec_revision != task["spec_revision"]:
            raise SDDError(f"stale specification revision {spec_revision}; current is {task['spec_revision']}")
        attempt_id = attempt_id or str(uuid.uuid4())
        with self._connect() as db:
            attempt_no = db.execute("SELECT COALESCE(MAX(attempt_no), 0) + 1 FROM attempts WHERE task_id = ?", (task_id,)).fetchone()[0]
            db.execute(
                "INSERT INTO attempts(attempt_id, task_id, attempt_no, actor, role, spec_revision, changed_files_json, checks_json, summary, state, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (attempt_id, task_id, attempt_no, actor, role, spec_revision, json_text(list(changed_files)), json_text(list(checks)), summary, state, utc_now()),
            )
        self.set_task_status(task_id, "review" if role == "engineer" else ("accepted" if state == "accepted" else "submitted"))
        return {"attempt_id": attempt_id, "attempt_no": attempt_no, "task_id": task_id}

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
        task = self.task(task_id)
        if not task:
            raise SDDError(f"unknown task: {task_id}")
        with self._connect() as db:
            attempts = [dict(row) for row in db.execute("SELECT * FROM attempts WHERE task_id = ? ORDER BY attempt_no", (task_id,))]
            evidence = [dict(row) for row in db.execute("SELECT e.* FROM evidence e JOIN attempts a ON a.attempt_id = e.attempt_id WHERE a.task_id = ?", (task_id,))]
        current = {item["criterion_id"] if "criterion_id" in item else item["id"]: item for item in required_criteria if item.get("required", True)}
        reasons: list[str] = []
        latest_by_criterion: dict[str, dict[str, Any]] = {}
        for item in evidence:
            latest_by_criterion[item["criterion_id"]] = item
        for criterion_id in current:
            item = latest_by_criterion.get(criterion_id)
            if not item:
                reasons.append(f"missing evidence for {criterion_id}")
                continue
            if item["exit_status"] != 0:
                reasons.append(f"verification failed for {criterion_id} (exit {item['exit_status']})")
            if item["content_fingerprint"] != file_fingerprint(root, json.loads(next(a for a in attempts if a["attempt_id"] == item["attempt_id"])["changed_files_json"])):
                reasons.append(f"evidence is stale for {criterion_id}; changed files no longer match")
        if not any(a["role"] == "reviewer" and a["state"] in ("accepted", "submitted") for a in attempts):
            reasons.append("independent reviewer submission is missing")
        accepted = not reasons
        if accepted:
            self.set_task_status(task_id, "accepted")
        return {"accepted": accepted, "task_id": task_id, "reasons": reasons, "criteria": sorted(current), "evidence_count": len(evidence)}

    def accept_project(self, required_criteria: Sequence[Mapping[str, Any]], root: Path) -> dict[str, Any]:
        """Evaluate the whole project, independent of native board card state."""
        project_id = self.project_id()
        if not project_id:
            raise SDDError("project is not initialized")
        with self._connect() as db:
            attempts = [dict(row) for row in db.execute(
                "SELECT a.*, t.role AS task_role FROM attempts a JOIN tasks t ON t.task_id = a.task_id WHERE t.project_id = ? ORDER BY a.attempt_no",
                (project_id,),
            )]
            evidence = [dict(row) for row in db.execute(
                "SELECT e.*, a.changed_files_json, a.spec_revision FROM evidence e JOIN attempts a ON a.attempt_id = e.attempt_id JOIN tasks t ON t.task_id = a.task_id WHERE t.project_id = ?",
                (project_id,),
            )]
        required = {item.get("id", item.get("criterion_id")): item for item in required_criteria if item.get("required", True)}
        reasons: list[str] = []
        latest: dict[str, dict[str, Any]] = {}
        for item in evidence:
            latest[item["criterion_id"]] = item
        for criterion_id in required:
            item = latest.get(criterion_id)
            if not item:
                reasons.append(f"missing evidence for {criterion_id}")
                continue
            if item["exit_status"] != 0:
                reasons.append(f"verification failed for {criterion_id} (exit {item['exit_status']})")
            changed_files = json.loads(item["changed_files_json"])
            if item["content_fingerprint"] != file_fingerprint(root, changed_files):
                reasons.append(f"evidence is stale for {criterion_id}; changed files no longer match")
            if item["spec_revision"] != 1:
                reasons.append(f"evidence for {criterion_id} targets an obsolete specification")
        if not any(item["role"] == "reviewer" and item["state"] in ("accepted", "submitted") for item in attempts):
            reasons.append("independent reviewer submission is missing")
        if not any(item["role"] == "engineer" for item in attempts):
            reasons.append("engineer submission is missing")
        accepted = not reasons
        if accepted:
            with self._connect() as db:
                db.execute("UPDATE projects SET stage = 'accepted', updated_at = ? WHERE project_id = ?", (utc_now(), project_id))
        return {"accepted": accepted, "project_id": project_id, "reasons": reasons, "criteria": sorted(required), "evidence_count": len(evidence)}

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
            current = db.execute("SELECT holder, expires_at FROM leases WHERE project_id = ?", (project_id,)).fetchone()
            if current and current["expires_at"] > now and current["holder"] != holder:
                return False
            db.execute("INSERT OR REPLACE INTO leases(project_id, holder, expires_at, acquired_at) VALUES(?,?,?,?)", (project_id, holder, now + ttl, now))
        return True

    def export_jsonl(self) -> Path:
        # Events are written as part of each committed append.  Return the stable path for callers.
        return self.paths.jsonl


class VerificationRunner:
    """Run explicit checks and persist their evidence; not an OS sandbox."""

    def __init__(self, ledger: Ledger, root: Path):
        self.ledger = ledger
        self.root = root

    def run(self, attempt_id: str, criterion_id: str, command: str, changed_files: Sequence[str], timeout: int = 300) -> dict[str, Any]:
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
        fingerprint = file_fingerprint(self.root, changed_files)
        evidence_id = self.ledger.add_evidence(attempt_id, criterion_id, "command", command, str(self.root), status, output, fingerprint)
        return {"evidence_id": evidence_id, "criterion_id": criterion_id, "exit_status": status, "duration_ms": int((time.monotonic() - started) * 1000), "output": output, "fingerprint_before": before, "fingerprint_after": fingerprint}
