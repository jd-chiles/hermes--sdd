"""Hermes SDD native plugin.

The plugin keeps the deterministic workflow kernel local and delegates worker
processes, board history, approvals, and terminal execution to Hermes through its
public plugin context.
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import uuid
from pathlib import Path
from typing import Any

from .bridge import HermesBridge
from .core import SCHEMA_VERSION, DEFAULT_LIMITS, Ledger, ProjectPaths, SDDError, VerificationRunner, repository_fingerprint
from .planning import Plan, build_plan, read_current_plan, write_spec
from .routing import classify_failure, recovery_decision, resolve_routes, route_from


PLUGIN_ROOT = Path(__file__).resolve().parent


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


class SDDService:
    def __init__(self, root: Path, bridge: HermesBridge | None = None, actor: str = "hermes-cli"):
        self.root = root.resolve()
        self.paths = ProjectPaths(self.root)
        self.ledger = Ledger(self.paths)
        self.bridge = bridge or HermesBridge()
        self.actor = actor

    def initialize(self, request: str, mode: str | None = None, execute: bool = False, limits: dict[str, int] | None = None, task_assessments: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
        plan = build_plan(request, mode, task_assessments)
        board_slug = f"sdd-{plan.slug}"
        initial_fingerprint = repository_fingerprint(self.root)
        project = self.ledger.init_project(request, plan.mode, plan.slug, board_slug, plan.criteria, plan.tasks, limits)
        replayed = project.pop('replayed', False)
        board_slug = project['board_slug']
        spec_path = write_spec(self.paths, plan, self.ledger)
        self.ledger.append_event(project["project_id"], "initial_repository_snapshot", {"fingerprint": initial_fingerprint}, f"{project['project_id']}:initial-repository-snapshot")
        if execute and not self.bridge.available():
            raise SDDError("plan saved; Hermes dispatch context is unavailable")
        if execute:
            self.ledger.set_stage("dispatching")
            board = self.sync_board(plan, board_slug)
        else:
            board = {"available": False, "message": "planning only"}
        return {"project": self.ledger.project(), "spec_path": str(spec_path), "plan": plan.__dict__, "board": board, "replayed": replayed}

    def sync_board(self, plan: Plan | None = None, board_slug: str | None = None) -> dict[str, Any]:
        if not plan:
            current = read_current_plan(self.ledger)
            project = self.ledger.project() or {}
            plan = Plan(current["mode"], project.get("board_slug", "sdd-project"), current["request"], current["criteria"], current["tasks"])
        board_slug = board_slug or (self.ledger.project() or {})["board_slug"]
        if (self.ledger.project() or {}).get("paused"):
            raise SDDError("project is paused")
        profiles = {
            task["role"]: f"Hermes SDD {task['role']} for repository planning, implementation, review, or acceptance"
            for task in plan.tasks
        }
        provisioned = self.bridge.provision_profiles(profiles)
        board = self.bridge.ensure_board(board_slug, f"Hermes SDD — {plan.slug}")
        native: dict[str, str] = {}
        recovered: set[str] = set()
        created: list[dict[str, Any]] = []
        queued: list[str] = []
        routing = self.routing()
        task_rows = {item["stable_key"]: item for item in self.ledger.tasks()}
        for task in plan.tasks:
            task_row = task_rows[task["stable_key"]]
            if task_row["native_task_id"]:
                native[task["stable_key"]] = task_row["native_task_id"]
                recovered.add(task["stable_key"])
                continue
            parent_keys = task.get("parent_keys", [task["parent_key"]] if task.get("parent_key") else [])
            # A newly created parent is still running. Its children remain queued
            # until the parent reports a terminal success through complete_task.
            terminal = {"completed", "accepted"}
            missing = [key for key in parent_keys if key not in native]
            if missing:
                queued.append(task["stable_key"])
                continue
            if any(key not in recovered and task_rows.get(key, {}).get("status") not in terminal for key in parent_keys):
                queued.append(task["stable_key"])
                continue
            parents = [native[key] for key in parent_keys]
            recovered_native_id = self.bridge.find_task(board_slug, task["stable_key"])
            if recovered_native_id:
                self.ledger.set_native_task_id(task_row["task_id"], recovered_native_id)
                operation_id = f"{self.ledger.project()['project_id']}:dispatch:{task['stable_key']}"
                self.ledger.complete_dispatch(operation_id, recovered_native_id) if self.ledger.dispatches() and any(item["operation_id"] == operation_id for item in self.ledger.dispatches()) else None
                native[task["stable_key"]] = recovered_native_id
                recovered.add(task["stable_key"])
                created.append({"stable_key": task["stable_key"], "native_task_id": recovered_native_id, "recovered": True})
                continue
            body = f"SDD project: {plan.slug}\nStable task: {task['stable_key']}\nRole: {task['role']}\nAcceptance criteria: {', '.join(c['id'] for c in plan.criteria)}\nDo not claim completion without submitting evidence through the SDD tools."
            route = routing.get("routes", {}).get(task.get("difficulty", {}).get("tier", "med"), {})
            operation_id = f"{self.ledger.project()['project_id']}:dispatch:{task['stable_key']}"
            existing_dispatch = next((item for item in self.ledger.dispatches() if item["operation_id"] == operation_id), None)
            if existing_dispatch and existing_dispatch["state"] == "pending":
                raise SDDError(f"dispatch for {task['stable_key']} is unresolved; reconcile before retry")
            limits = (self.ledger.project() or {}).get("limits", {})
            estimated_runtime = int(limits.get("estimated_runtime_seconds", DEFAULT_LIMITS["estimated_runtime_seconds"]))
            capacity = self.ledger.admit_capacity(task_row["task_id"], operation_id, self.actor, estimated_runtime)
            if not capacity.get("allowed"):
                raise SDDError(f"dispatch blocked by {capacity['blocked']}: {capacity['unblock_condition']}")
            intent = self.ledger.dispatch_intent(task_row["task_id"], task["stable_key"], operation_id, {"board": board_slug, "parents": parents, "assignee": task["role"]}, route)
            if intent.get("replayed") and intent.get("state") == "pending":
                raise SDDError(f"dispatch for {task['stable_key']} is unresolved; reconcile before retry")
            kwargs: dict[str, Any] = {"idempotency_key": operation_id}
            kwargs["max_retries"] = int(limits.get("max_native_retries", DEFAULT_LIMITS["max_native_retries"]))
            supported = inspect.signature(self.bridge.create_task).parameters
            kwargs = {key: value for key, value in kwargs.items() if key in supported}
            result = self.bridge.create_task(board_slug, task["title"], body, task["role"], parents, route, **kwargs) if route else self.bridge.create_task(board_slug, task["title"], body, task["role"], parents, **kwargs)
            native_id = self.bridge.decode_task_id(result.get("result") if isinstance(result, dict) else result)
            if not native_id:
                raise SDDError(f"native creation returned no ID for {task['stable_key']}; reconcile before retry")
            if native_id:
                self.ledger.set_native_task_id(task_row["task_id"], native_id)
                raw_receipt = result.get("result") if isinstance(result, dict) else result
                self.ledger.complete_dispatch(operation_id, native_id, self.bridge.effective_route(raw_receipt))
                native[task["stable_key"]] = native_id
            created.append({"stable_key": task["stable_key"], "native_task_id": native_id, "result": result, "effective_route": self.bridge.effective_route(result.get("result") if isinstance(result, dict) else result)})
        return {"profiles": provisioned, "board": board, "created": created, "queued": queued, "native_task_ids": native, "routing": routing}

    def routing(self) -> dict[str, Any]:
        raw = os.environ.get("HERMES_SDD_ROUTES_JSON")
        if not raw:
            return resolve_routes(None)
        try:
            config = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SDDError("HERMES_SDD_ROUTES_JSON is not valid JSON") from exc
        return resolve_routes(config)

    def status(self) -> dict[str, Any]:
        status = self.ledger.status()
        if status["initialized"]:
            plan = read_current_plan(self.ledger)
            assessments = {task["stable_key"]: task.get("difficulty") for task in plan["tasks"]}
            for task in status["tasks"]:
                task["difficulty"] = assessments.get(task["stable_key"])
            status["routing"] = self.routing()
            status["routing"]["effective_host_routes"] = "unverified"
            status["dispatches"] = self.ledger.dispatches()
            status["recovery_events"] = self.ledger.recovery_events()
            status["budgets"] = self.ledger.budgets()
            status["route_breakers"] = self.ledger.breakers()
            status["capacity"] = self.ledger.capacity()
            status["limit_blockers"] = self.ledger.blockers()
        return status

    def admit(self, task_id: str, files: list[str], operation_id: str) -> dict[str, Any]:
        owned = self.ledger.acquire_ownership(task_id, self.actor, files, operation_id)
        return {"task_id": task_id, "owner": self.actor, "files": owned, "operation_id": operation_id}

    def submit(self, task_id: str, spec_revision: int, changed_files: list[str], checks: list[str], summary: str, role: str | None = None, attempt_id: str | None = None, verdict: str | None = None) -> dict[str, Any]:
        task = self.ledger.task(task_id)
        if not task:
            raise SDDError(f"unknown task: {task_id}")
        expected_role = task["role"]
        if role and role != expected_role:
            raise SDDError(f"role mismatch: task requires {expected_role}; submission claimed {role}")
        if self.actor not in (expected_role, f"sdd-{expected_role}", "hermes-cli", "coordinator"):
            raise SDDError(f"host identity {self.actor!r} is not authorized for {expected_role} task {task_id}")
        if expected_role == "reviewer":
            verdict = verdict or "approve"
            if verdict not in {"approve", "request_changes"}:
                raise SDDError("review verdict must be approve or request_changes")
        state = "accepted" if expected_role == "reviewer" and verdict == "approve" else "submitted"
        return self.ledger.create_attempt(task_id, self.actor, expected_role, spec_revision, changed_files, checks, summary, state, attempt_id, verdict)

    def verify(self, attempt_id: str, criterion_id: str, command: str, changed_files: list[str], timeout: int = 300) -> dict[str, Any]:
        return VerificationRunner(self.ledger, self.root).run(attempt_id, criterion_id, command, changed_files, timeout)

    def accept(self) -> dict[str, Any]:
        plan = read_current_plan(self.ledger)
        return self.ledger.accept_project(plan["criteria"], self.root)

    def close(self) -> dict[str, Any]:
        return self.ledger.close_project()

    def doctor(self) -> dict[str, Any]:
        status = self.ledger.status()
        return {"plugin": "hermes-sdd", "root": str(self.root), "initialized": status["initialized"], "ledger": str(self.paths.database), "ledger_schema": SCHEMA_VERSION, "native_dispatch": self.bridge.available(), "limits": DEFAULT_LIMITS, "notes": ["Hermes owns worker processes, approvals, and Kanban persistence.", "The SDD ownership ledger is coordination metadata, not an OS security sandbox.", "Profiles and managed dependency adapters must be exercised against the target Hermes release before publication."]}

    def pause(self) -> dict[str, Any]:
        project = self.ledger.project()
        if project:
            for task in self.ledger.tasks():
                if task["native_task_id"] and task["status"] in {"queued", "running", "review", "submitted"}:
                    self.bridge.transition_task(project["board_slug"], task["native_task_id"], "block", "SDD pause requested; progress is preserved")
        self.ledger.set_stage("paused", paused=True)
        return self.status()

    def resume(self) -> dict[str, Any]:
        project = self.ledger.project()
        if project:
            for task in self.ledger.tasks():
                if task["native_task_id"] and task["status"] in {"queued", "running", "review", "submitted"}:
                    self.bridge.transition_task(project["board_slug"], task["native_task_id"], "unblock")
        self.ledger.set_stage("reconciling", paused=False)
        return self.status()

    def recover(self) -> dict[str, Any]:
        current = self.ledger.status()
        if not current["initialized"]:
            return {"recovered": False, "blocked": "project is not initialized", "status": current}
        if current["project"]["paused"]:
            return {"recovered": False, "blocked": "project is paused", "status": current}
        if not self.bridge.available():
            return {"recovered": False, "blocked": "Hermes dispatch context is unavailable", "status": current}
        holder = f"recovery:{uuid.uuid4()}"
        if not self.ledger.acquire_lease(holder):
            return {"recovered": False, "blocked": "another coordinator currently holds the project lease", "status": self.status()}
        try:
            self.ledger.export_jsonl()
            self.ledger.set_stage("reconciling")
            synced = self.sync_board()
            self.ledger.set_stage("dispatching")
            return {"recovered": True, "synced": synced, "status": self.status()}
        finally:
            self.ledger.release_lease(holder)

    def record_failure(self, task_id: str, code: str, phase: str = "dispatch", route_identity: str = "unknown", retry_after: int | None = None) -> dict[str, Any]:
        failure = classify_failure(code, phase)
        decision = recovery_decision(failure["class"], route_identity)
        if retry_after is not None:
            decision["retry_after_seconds"] = max(0, int(retry_after))
        return self.ledger.record_recovery(task_id, failure, decision, route_identity, retry_after)

    def admit_recovery(self, task_id: str, failure_class: str, route_identity: str, actionable_change: str | None) -> dict[str, Any]:
        return self.ledger.recovery_admission(task_id, failure_class, route_identity, actionable_change)

    def recover_task(self, task_id: str, failure_class: str, route_identity: str, actionable_change: str) -> dict[str, Any]:
        """Reserve recovery budget before promoting a blocked native task."""
        task = self.ledger.task(task_id)
        project = self.ledger.project()
        if not task or not project or not task.get("native_task_id"):
            return {"admitted": False, "blocked": "native task receipt is required before recovery"}
        admission = self.ledger.recovery_admission(task_id, failure_class, route_identity, actionable_change)
        if not admission.get("allowed"):
            return {"admitted": False, "admission": admission}
        result = self.bridge.promote_task(project["board_slug"], task["native_task_id"], actionable_change)
        try:
            receipt = HermesBridge.decode_response(result)
        except SDDError:
            self.record_failure(task_id, "unknown_or_ambiguous", "recovery", route_identity)
            raise
        return {"admitted": True, "admission": admission, "native_task_id": task["native_task_id"], "result": receipt}

    def complete_task(self, operation_id: str, actual_seconds: int, state: str = "completed") -> dict[str, Any]:
        result = self.ledger.complete_capacity(operation_id, actual_seconds, state)
        if state == "completed":
            reservation = self.ledger.reservation(operation_id)
            if reservation:
                self.ledger.set_task_status(reservation["task_id"], "completed")
                try:
                    result["promoted"] = self.sync_board().get("created", [])
                except SDDError as exc:
                    result["promotion_blocked"] = str(exc)
        return result


def _root_from_params(params: dict[str, Any]) -> Path:
    return Path(params.get("project_root") or os.getcwd()).expanduser().resolve()


def _service(ctx: Any, params: dict[str, Any]) -> SDDService:
    actor = getattr(ctx, "profile_name", None) or os.environ.get("HERMES_PROFILE") or "hermes-cli"
    dispatch = getattr(ctx, "dispatch_tool", None)
    bridge = HermesBridge(dispatch=dispatch if callable(dispatch) else None)
    return SDDService(_root_from_params(params), bridge, actor)


def _handle_tool(ctx: Any, name: str, params: dict[str, Any]) -> str:
    try:
        service = _service(ctx, params)
        if name == "initialize":
            result = service.initialize(params["request"], params.get("mode"), bool(params.get("execute", False)), params.get("limits"), params.get("task_assessments"))
        elif name == "status":
            result = service.status()
        elif name == "admit":
            result = service.admit(params["task_id"], params.get("files", []), params.get("operation_id") or os.urandom(8).hex())
        elif name == "submit":
            result = service.submit(params["task_id"], int(params["spec_revision"]), params.get("changed_files", []), params.get("checks", []), params["summary"], params.get("role"), params.get("attempt_id"), params.get("verdict"))
        elif name == "verify":
            result = service.verify(params["attempt_id"], params["criterion_id"], params["command"], params.get("changed_files", []), int(params.get("timeout", 300)))
        elif name == "accept":
            result = service.accept()
        elif name == "close":
            result = service.close()
        elif name == "doctor":
            result = service.doctor()
        elif name == "pause":
            result = service.pause()
        elif name == "resume":
            result = service.resume()
        elif name == "recover":
            result = service.recover()
        elif name == "admit_recovery":
            result = service.admit_recovery(params["task_id"], params["failure_class"], params["route_identity"], params.get("actionable_change"))
        elif name == "recover_task":
            result = service.recover_task(params["task_id"], params["failure_class"], params["route_identity"], params["actionable_change"])
        elif name == "complete_task":
            result = service.complete_task(params["operation_id"], int(params["actual_seconds"]), params.get("state", "completed"))
        else:
            raise SDDError(f"unknown SDD operation: {name}")
        return _json(result)
    except (SDDError, OSError, ValueError) as exc:
        return _json({"ok": False, "error": str(exc)})


def _schemas() -> dict[str, dict[str, Any]]:
    root = {"type": "string", "description": "Repository root; defaults to Hermes' current working directory."}
    return {
        "initialize": {"name": "sdd_initialize", "description": "Create or reconcile an SDD specification and stable task graph for a local repository request.", "parameters": {"type": "object", "properties": {"request": {"type": "string"}, "mode": {"type": "string", "enum": ["bugfix", "feature", "product"]}, "execute": {"type": "boolean"}, "task_assessments": {"type": "object", "description": "Per stable task key: dimensions (scope, uncertainty, coupling, consequence, verification) rated low/med/high, rationale, optional upward override."}, "project_root": root}, "required": ["request"]}},
        "status": {"name": "sdd_status", "description": "Show SDD stage, workers, task assignments, file ownership, checks, and blockers.", "parameters": {"type": "object", "properties": {"project_root": root}}},
        "admit": {"name": "sdd_admit_task", "description": "Atomically acquire explicit file ownership for an SDD task; overlapping ownership is rejected.", "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}}, "operation_id": {"type": "string"}, "project_root": root}, "required": ["task_id", "files"]}},
        "submit": {"name": "sdd_submit_result", "description": "Submit an immutable worker result for SDD evaluation. Reviewer submissions require an explicit approve or request_changes verdict.", "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}, "attempt_id": {"type": "string"}, "spec_revision": {"type": "integer"}, "changed_files": {"type": "array", "items": {"type": "string"}}, "checks": {"type": "array", "items": {"type": "string"}}, "summary": {"type": "string"}, "role": {"type": "string"}, "verdict": {"type": "string", "enum": ["approve", "request_changes"]}, "project_root": root}, "required": ["task_id", "spec_revision", "summary"]}},
        "verify": {"name": "sdd_verify", "description": "Execute one explicit repository verification command and store immutable evidence with content fingerprints.", "parameters": {"type": "object", "properties": {"attempt_id": {"type": "string"}, "criterion_id": {"type": "string"}, "command": {"type": "string"}, "changed_files": {"type": "array", "items": {"type": "string"}}, "timeout": {"type": "integer"}, "project_root": root}, "required": ["attempt_id", "criterion_id", "command"]}},
        "accept": {"name": "sdd_accept", "description": "Evaluate project acceptance: required evidence, passing checks, current fingerprints, engineer result, and independent review.", "parameters": {"type": "object", "properties": {"project_root": root}}},
        "close": {"name": "sdd_close", "description": "Close an accepted SDD request while preserving its ledger and evidence history for future requests.", "parameters": {"type": "object", "properties": {"project_root": root}}},
        "doctor": {"name": "sdd_doctor", "description": "Diagnose SDD installation, ledger, native dispatch, and compatibility notes.", "parameters": {"type": "object", "properties": {"project_root": root}}},
        "pause": {"name": "sdd_pause", "description": "Pause SDD dispatch while preserving durable progress.", "parameters": {"type": "object", "properties": {"project_root": root}}},
        "resume": {"name": "sdd_resume", "description": "Resume and reconcile a paused SDD project.", "parameters": {"type": "object", "properties": {"project_root": root}}},
        "recover": {"name": "sdd_recover", "description": "Reconcile native Kanban references and the SDD ledger after interruption using a project-scoped lease.", "parameters": {"type": "object", "properties": {"project_root": root}}},
        "admit_recovery": {"name": "sdd_admit_recovery", "description": "Reserve a durable repair or provider-recovery budget only when the failure and recovery change are admissible.", "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}, "failure_class": {"type": "string"}, "route_identity": {"type": "string"}, "actionable_change": {"type": "string"}, "project_root": root}, "required": ["task_id", "failure_class", "route_identity"]}},
        "recover_task": {"name": "sdd_recover_task", "description": "Admit a durable recovery and promote its existing native task without creating a duplicate.", "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}, "failure_class": {"type": "string"}, "route_identity": {"type": "string"}, "actionable_change": {"type": "string"}, "project_root": root}, "required": ["task_id", "failure_class", "route_identity", "actionable_change"]}},
        "complete_task": {"name": "sdd_complete_task", "description": "Release a worker/runtime reservation with actual runtime accounting after a native task reaches a terminal state.", "parameters": {"type": "object", "properties": {"operation_id": {"type": "string"}, "actual_seconds": {"type": "integer"}, "state": {"type": "string", "enum": ["completed", "failed", "released", "ambiguous"]}, "project_root": root}, "required": ["operation_id", "actual_seconds"]}},
    }


def _slash(ctx: Any, raw_args: str) -> str:
    tokens = raw_args.strip().split(maxsplit=1)
    if not tokens:
        return _handle_tool(ctx, "status", {})
    command = tokens[0]
    rest = tokens[1] if len(tokens) == 2 else ""
    if command in {"status", "doctor", "pause", "resume", "recover", "accept", "close"}:
        return _handle_tool(ctx, command, {})
    if command in {"plan", "build", "fix"}:
        if not rest:
            return _json({"ok": False, "error": f"Usage: /sdd {command} <request>"})
        return _handle_tool(ctx, "initialize", {"request": rest, "mode": "bugfix" if command == "fix" else None, "execute": command in {"build", "fix"}})
    # The bare form is the normal journey: classify, plan, and execute.
    return _handle_tool(ctx, "initialize", {"request": raw_args.strip(), "execute": True})


def _cli_setup(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="sdd_command")
    for name in ("status", "doctor", "pause", "resume", "recover", "accept", "close"):
        command = sub.add_parser(name)
        command.add_argument("--project-root", default=None)
    for name in ("plan", "build", "fix"):
        command = sub.add_parser(name)
        command.add_argument("request")
        command.add_argument("--project-root", default=None)
    parser.set_defaults(func=_cli_handler)


def _cli_handler(args: argparse.Namespace) -> None:
    root = Path(getattr(args, "project_root", None) or os.getcwd()).resolve()
    command = args.sdd_command or "status"
    context = type("CLIContext", (), {})()
    if command in {"status", "doctor", "pause", "resume", "recover", "accept", "close"}:
        result = _handle_tool(context, command, {"project_root": str(root)})
    else:
        result = _handle_tool(context, "initialize", {"project_root": str(root), "request": args.request, "mode": "bugfix" if command == "fix" else None, "execute": command in {"build", "fix"}})
    print(result)


def register(ctx: Any) -> None:
    """Called once by Hermes' plugin loader."""
    for operation, schema in _schemas().items():
        ctx.register_tool(name=schema["name"], toolset="sdd", schema=schema, handler=lambda params, _operation=operation, **kwargs: _handle_tool(ctx, _operation, params))
    ctx.register_command("sdd", lambda raw: _slash(ctx, raw), description="Plan and verify local repository changes with SDD", args_hint="plan|build|fix <request> | status | pause | resume | recover | doctor")
    ctx.register_cli_command(name="sdd", help="Plan and verify local repository changes with SDD", setup_fn=_cli_setup, handler_fn=_cli_handler)
    for skill_path in sorted((PLUGIN_ROOT.parent / "skills").glob("*/SKILL.md")):
        ctx.register_skill(skill_path.parent.name, skill_path)
