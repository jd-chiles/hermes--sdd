"""Hermes SDD Team native plugin.

The plugin keeps the deterministic workflow kernel local and delegates worker
processes, board history, approvals, and terminal execution to Hermes through its
public plugin context.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .bridge import HermesBridge
from .core import DEFAULT_LIMITS, Ledger, ProjectPaths, SDDError, VerificationRunner, repository_fingerprint
from .planning import Plan, build_plan, read_current_plan, write_spec


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

    def initialize(self, request: str, mode: str | None = None, execute: bool = False, limits: dict[str, int] | None = None) -> dict[str, Any]:
        plan = build_plan(request, mode)
        board_slug = f"sdd-{plan.slug}"
        initial_fingerprint = repository_fingerprint(self.root)
        project = self.ledger.init_project(request, plan.mode, plan.slug, board_slug, plan.criteria, plan.tasks, limits)
        spec_path = write_spec(self.paths, plan, self.ledger)
        self.ledger.append_event(project["project_id"], "initial_repository_snapshot", {"fingerprint": initial_fingerprint}, f"{project['project_id']}:initial-repository-snapshot")
        if execute:
            self.ledger.set_stage("dispatching")
            board = self.sync_board(plan, board_slug)
        else:
            self.ledger.set_stage("planned")
            board = {"available": False, "message": "planning only"}
        return {"project": self.ledger.project(), "spec_path": str(spec_path), "plan": plan.__dict__, "board": board}

    def sync_board(self, plan: Plan | None = None, board_slug: str | None = None) -> dict[str, Any]:
        if not plan:
            current = read_current_plan(self.ledger)
            project = self.ledger.project() or {}
            plan = Plan(current["mode"], project.get("board_slug", "sdd-project"), current["request"], current["criteria"], current["tasks"])
        board_slug = board_slug or (self.ledger.project() or {})["board_slug"]
        profiles = {
            task["role"]: f"Hermes SDD {task['role']} for repository planning, implementation, review, or acceptance"
            for task in plan.tasks
        }
        provisioned = self.bridge.provision_profiles(profiles)
        board = self.bridge.ensure_board(board_slug, f"Hermes SDD — {plan.slug}")
        native: dict[str, str] = {}
        created: list[dict[str, Any]] = []
        for task in plan.tasks:
            task_row = next(item for item in self.ledger.tasks() if item["stable_key"] == task["stable_key"])
            if task_row["native_task_id"]:
                native[task["stable_key"]] = task_row["native_task_id"]
                continue
            parents = [native[task["parent_key"]]] if task.get("parent_key") in native else []
            body = f"SDD project: {plan.slug}\nStable task: {task['stable_key']}\nRole: {task['role']}\nAcceptance criteria: {', '.join(c['id'] for c in plan.criteria)}\nDo not claim completion without submitting evidence through the SDD tools."
            result = self.bridge.create_task(board_slug, task["title"], body, task["role"], parents)
            native_id = self.bridge.decode_task_id(result.get("result") if isinstance(result, dict) else result)
            if native_id:
                self.ledger.set_native_task_id(task_row["task_id"], native_id)
                native[task["stable_key"]] = native_id
            created.append({"stable_key": task["stable_key"], "native_task_id": native_id, "result": result})
        return {"profiles": provisioned, "board": board, "created": created, "native_task_ids": native}

    def status(self) -> dict[str, Any]:
        return self.ledger.status()

    def admit(self, task_id: str, files: list[str], operation_id: str) -> dict[str, Any]:
        owned = self.ledger.acquire_ownership(task_id, self.actor, files, operation_id)
        self.ledger.set_task_status(task_id, "running")
        return {"task_id": task_id, "owner": self.actor, "files": owned, "operation_id": operation_id}

    def submit(self, task_id: str, spec_revision: int, changed_files: list[str], checks: list[str], summary: str, role: str | None = None, attempt_id: str | None = None) -> dict[str, Any]:
        task = self.ledger.task(task_id)
        if not task:
            raise SDDError(f"unknown task: {task_id}")
        expected_role = task["role"]
        if role and role != expected_role:
            raise SDDError(f"role mismatch: task requires {expected_role}; submission claimed {role}")
        if self.actor not in (expected_role, f"sdd-{expected_role}", "hermes-cli", "coordinator"):
            raise SDDError(f"host identity {self.actor!r} is not authorized for {expected_role} task {task_id}")
        state = "accepted" if expected_role == "reviewer" else "submitted"
        return self.ledger.create_attempt(task_id, self.actor, expected_role, spec_revision, changed_files, checks, summary, state, attempt_id)

    def verify(self, attempt_id: str, criterion_id: str, command: str, changed_files: list[str], timeout: int = 300) -> dict[str, Any]:
        return VerificationRunner(self.ledger, self.root).run(attempt_id, criterion_id, command, changed_files, timeout)

    def accept(self) -> dict[str, Any]:
        plan = read_current_plan(self.ledger)
        return self.ledger.accept_project(plan["criteria"], self.root)

    def doctor(self) -> dict[str, Any]:
        status = self.ledger.status()
        return {"plugin": "hermes-sdd-team", "root": str(self.root), "initialized": status["initialized"], "ledger": str(self.paths.database), "ledger_schema": 1, "native_dispatch": self.bridge.available(), "limits": DEFAULT_LIMITS, "notes": ["Hermes owns worker processes, approvals, and Kanban persistence.", "The SDD ownership ledger is coordination metadata, not an OS security sandbox.", "Profiles and managed dependency adapters must be exercised against the target Hermes release before publication."]}

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
        holder = f"recovery:{os.getpid()}"
        if not self.ledger.acquire_lease(holder):
            return {"recovered": False, "blocked": "another coordinator currently holds the project lease", "status": self.status()}
        current = self.ledger.status()
        if not current["initialized"]:
            return {"recovered": False, "blocked": "project is not initialized", "status": current}
        self.ledger.set_stage("reconciling")
        synced = self.sync_board()
        self.ledger.set_stage("dispatching")
        return {"recovered": True, "synced": synced, "status": self.status()}


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
            result = service.initialize(params["request"], params.get("mode"), bool(params.get("execute", False)), params.get("limits"))
        elif name == "status":
            result = service.status()
        elif name == "admit":
            result = service.admit(params["task_id"], params.get("files", []), params.get("operation_id") or os.urandom(8).hex())
        elif name == "submit":
            result = service.submit(params["task_id"], int(params["spec_revision"]), params.get("changed_files", []), params.get("checks", []), params["summary"], params.get("role"), params.get("attempt_id"))
        elif name == "verify":
            result = service.verify(params["attempt_id"], params["criterion_id"], params["command"], params.get("changed_files", []), int(params.get("timeout", 300)))
        elif name == "accept":
            result = service.accept()
        elif name == "doctor":
            result = service.doctor()
        elif name == "pause":
            result = service.pause()
        elif name == "resume":
            result = service.resume()
        elif name == "recover":
            result = service.recover()
        else:
            raise SDDError(f"unknown SDD operation: {name}")
        return _json(result)
    except (SDDError, OSError, ValueError) as exc:
        return _json({"ok": False, "error": str(exc)})


def _schemas() -> dict[str, dict[str, Any]]:
    root = {"type": "string", "description": "Repository root; defaults to Hermes' current working directory."}
    return {
        "initialize": {"name": "sdd_initialize", "description": "Create or reconcile an SDD specification and stable task graph for a local repository request.", "parameters": {"type": "object", "properties": {"request": {"type": "string"}, "mode": {"type": "string", "enum": ["bugfix", "feature", "product"]}, "execute": {"type": "boolean"}, "project_root": root}, "required": ["request"]}},
        "status": {"name": "sdd_status", "description": "Show SDD stage, workers, task assignments, file ownership, checks, and blockers.", "parameters": {"type": "object", "properties": {"project_root": root}}},
        "admit": {"name": "sdd_admit_task", "description": "Atomically acquire explicit file ownership for an SDD task; overlapping ownership is rejected.", "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}}, "operation_id": {"type": "string"}, "project_root": root}, "required": ["task_id", "files"]}},
        "submit": {"name": "sdd_submit_result", "description": "Submit an immutable worker result for SDD evaluation. Completion is not acceptance.", "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}, "attempt_id": {"type": "string"}, "spec_revision": {"type": "integer"}, "changed_files": {"type": "array", "items": {"type": "string"}}, "checks": {"type": "array", "items": {"type": "string"}}, "summary": {"type": "string"}, "role": {"type": "string"}, "project_root": root}, "required": ["task_id", "spec_revision", "summary"]}},
        "verify": {"name": "sdd_verify", "description": "Execute one explicit repository verification command and store immutable evidence with content fingerprints.", "parameters": {"type": "object", "properties": {"attempt_id": {"type": "string"}, "criterion_id": {"type": "string"}, "command": {"type": "string"}, "changed_files": {"type": "array", "items": {"type": "string"}}, "timeout": {"type": "integer"}, "project_root": root}, "required": ["attempt_id", "criterion_id", "command"]}},
        "accept": {"name": "sdd_accept", "description": "Evaluate project acceptance: required evidence, passing checks, current fingerprints, engineer result, and independent review.", "parameters": {"type": "object", "properties": {"project_root": root}}},
        "doctor": {"name": "sdd_doctor", "description": "Diagnose SDD installation, ledger, native dispatch, and compatibility notes.", "parameters": {"type": "object", "properties": {"project_root": root}}},
        "pause": {"name": "sdd_pause", "description": "Pause SDD dispatch while preserving durable progress.", "parameters": {"type": "object", "properties": {"project_root": root}}},
        "resume": {"name": "sdd_resume", "description": "Resume and reconcile a paused SDD project.", "parameters": {"type": "object", "properties": {"project_root": root}}},
        "recover": {"name": "sdd_recover", "description": "Reconcile native Kanban references and the SDD ledger after interruption using a project-scoped lease.", "parameters": {"type": "object", "properties": {"project_root": root}}},
    }


def _slash(ctx: Any, raw_args: str) -> str:
    tokens = raw_args.strip().split(maxsplit=1)
    if not tokens:
        return _handle_tool(ctx, "status", {})
    command = tokens[0]
    rest = tokens[1] if len(tokens) == 2 else ""
    if command in {"status", "doctor", "pause", "resume", "recover", "accept"}:
        return _handle_tool(ctx, command, {})
    if command in {"plan", "build", "fix"}:
        if not rest:
            return _json({"ok": False, "error": f"Usage: /sdd {command} <request>"})
        return _handle_tool(ctx, "initialize", {"request": rest, "mode": "bugfix" if command == "fix" else None, "execute": command == "build"})
    # The bare form is the normal journey: classify, plan, and execute.
    return _handle_tool(ctx, "initialize", {"request": raw_args.strip(), "execute": True})


def _cli_setup(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="sdd_command")
    for name in ("status", "doctor", "pause", "resume", "recover", "accept"):
        command = sub.add_parser(name)
        command.add_argument("--project-root", default=None)
    for name in ("plan", "build", "fix"):
        command = sub.add_parser(name)
        command.add_argument("request")
        command.add_argument("--project-root", default=None)
    parser.set_defaults(func=_cli_handler)


def _cli_handler(args: argparse.Namespace) -> None:
    root = Path(args.project_root or os.getcwd()).resolve()
    command = args.sdd_command
    context = type("CLIContext", (), {})()
    if command in {"status", "doctor", "pause", "resume", "recover", "accept"}:
        result = _handle_tool(context, command, {"project_root": str(root)})
    else:
        result = _handle_tool(context, "initialize", {"project_root": str(root), "request": args.request, "mode": "bugfix" if command == "fix" else None, "execute": command == "build"})
    print(result)


def register(ctx: Any) -> None:
    """Called once by Hermes' plugin loader."""
    for operation, schema in _schemas().items():
        ctx.register_tool(name=schema["name"], toolset="sdd", schema=schema, handler=lambda params, _operation=operation, **kwargs: _handle_tool(ctx, _operation, params))
    ctx.register_command("sdd", lambda raw: _slash(ctx, raw), description="Plan and verify local repository changes with SDD", args_hint="plan|build|fix <request> | status | pause | resume | recover | doctor")
    ctx.register_cli_command(name="sdd", help="Plan and verify local repository changes with SDD", setup_fn=_cli_setup, handler_fn=_cli_handler)
    for skill_path in sorted((PLUGIN_ROOT.parent / "skills").glob("*/SKILL.md")):
        ctx.register_skill(skill_path.parent.name, skill_path)
