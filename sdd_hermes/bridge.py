"""Small adapter around Hermes-owned capabilities.

The adapter deliberately never writes Hermes' databases.  It uses the documented
tool dispatch boundary and explicit board arguments so the user's selected board
cannot accidentally receive this project's tasks.
"""

from __future__ import annotations

import json
import shlex
from typing import Any, Callable

from .core import SDDError


class HermesBridge:
    def __init__(self, dispatch: Callable[[str, dict[str, Any]], Any] | None = None):
        self.dispatch = dispatch

    def available(self) -> bool:
        return self.dispatch is not None

    def terminal(self, command: str) -> Any:
        if not self.dispatch:
            return {"available": False, "reason": "Hermes dispatch context is unavailable"}
        return self.dispatch("terminal", {"command": command})

    def ensure_board(self, board_slug: str, display_name: str) -> dict[str, Any]:
        if not self.dispatch:
            return {"available": False, "board_slug": board_slug}
        command = "hermes kanban boards create {slug} --name {name} --description {description}".format(
            slug=shlex.quote(board_slug),
            name=shlex.quote(display_name),
            description=shlex.quote("Hermes SDD project board; owned by the SDD plugin"),
        )
        result = self.terminal(command)
        return {"available": True, "board_slug": board_slug, "result": result}

    def provision_profiles(self, profiles: dict[str, str]) -> list[dict[str, Any]]:
        """Create missing role profiles without cloning or editing user profiles.

        `profile create` is intentionally idempotent from the plugin's point of
        view: an already-existing profile returns a host error but is preserved.
        Enabling the installed plugin is attempted separately so a profile that
        existed before SDD can still participate.
        """
        if not self.dispatch:
            return [{"available": False, "profile": name} for name in profiles]
        results: list[dict[str, Any]] = []
        for name, description in profiles.items():
            create = self.terminal(
                "hermes profile create {name} --no-alias --no-skills --description {description}".format(
                    name=shlex.quote(name), description=shlex.quote(description)
                )
            )
            enable = self.terminal(f"hermes -p {shlex.quote(name)} plugins enable hermes-sdd-team")
            results.append({"profile": name, "create": create, "enable": enable})
        return results

    def create_task(self, board_slug: str, title: str, body: str, assignee: str, parents: list[str] | None = None, route: dict[str, Any] | None = None, idempotency_key: str | None = None, max_retries: int | None = None) -> dict[str, Any]:
        if not self.dispatch:
            return {"available": False}
        command = f"hermes kanban --board {shlex.quote(board_slug)} create {shlex.quote(title)} --body {shlex.quote(body)} --assignee {shlex.quote(assignee)} --completion-contract local-only --json"
        for parent in parents or []:
            command += f" --parent {shlex.quote(parent)}"
        if route:
            if route.get("provider"):
                command += f" --provider {shlex.quote(str(route['provider']))}"
            if route.get("model"):
                command += f" --model {shlex.quote(str(route['model']))}"
        if idempotency_key:
            command += f" --idempotency-key {shlex.quote(idempotency_key)}"
        if max_retries is not None:
            command += f" --max-retries {int(max_retries)}"
        raw = self.terminal(command)
        return {"available": True, "result": raw}

    @staticmethod
    def effective_route(result: Any) -> dict[str, Any] | None:
        """Extract a host receipt; absence is intentionally unverified."""
        decoded = HermesBridge.decode_response(result)
        if not isinstance(decoded, dict):
            return None
        route = decoded.get("effective_route") or decoded.get("route")
        return dict(route) if isinstance(route, dict) else None

    @staticmethod
    def retry_after_seconds(result: Any) -> int | None:
        """Read a structured retry delay without interpreting worker prose."""
        decoded = HermesBridge.decode_response(result)
        if not isinstance(decoded, dict):
            return None
        value = decoded.get("retry_after")
        if value is None and isinstance(decoded.get("headers"), dict):
            value = decoded["headers"].get("retry-after") or decoded["headers"].get("Retry-After")
        try:
            return max(0, int(value)) if value is not None else None
        except (TypeError, ValueError):
            return None

    def find_task(self, board_slug: str, stable_key: str) -> str | None:
        """Find an already-created task during recovery using its stable body key."""
        if not self.dispatch:
            return None
        raw = self.decode_response(self.terminal(f"hermes kanban --board {shlex.quote(board_slug)} list --json"))
        candidates = raw if isinstance(raw, list) else raw.get("tasks", raw.get("items")) if isinstance(raw, dict) else None
        if not isinstance(candidates, list):
            raise SDDError("invalid native task list; recovery cannot safely create tasks")
        matches = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise SDDError("invalid native task entry")
            markers = [line.strip() for line in str(candidate.get("body", "")).splitlines()]
            if f"Stable task: {stable_key}" in markers or candidate.get("stable_key") == stable_key:
                task_id = self.decode_task_id(candidate)
                if not task_id:
                    raise SDDError("matched native task has no ID")
                matches.append(task_id)
        if len(matches) > 1:
            raise SDDError(f"ambiguous native tasks for {stable_key}; manual reconciliation required")
        return matches[0] if matches else None

    def transition_task(self, board_slug: str, native_task_id: str, action: str, reason: str = "") -> Any:
        if action not in {"block", "unblock"}:
            raise ValueError(f"unsupported Kanban transition: {action}")
        if not self.dispatch:
            return {"available": False}
        command = f"hermes kanban --board {shlex.quote(board_slug)} {action} {shlex.quote(native_task_id)}"
        if action == "block":
            command += f" {shlex.quote(reason or 'SDD pause requested')}"
        return self.terminal(command)

    def promote_task(self, board_slug: str, native_task_id: str, reason: str = "SDD recovery admitted") -> Any:
        if not self.dispatch:
            return {"available": False}
        command = f"hermes kanban --board {shlex.quote(board_slug)} promote {shlex.quote(native_task_id)} {shlex.quote(reason)} --json"
        return self.terminal(command)

    @staticmethod
    def decode_response(result: Any) -> Any:
        for _ in range(8):
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError as exc:
                    raise SDDError("native response is not valid JSON") from exc
            elif isinstance(result, dict):
                if result.get("error") or result.get("available") is False or result.get("ok") is False:
                    raise SDDError("native operation failed or dispatch is unavailable")
                if "exit_code" in result:
                    if result["exit_code"] != 0:
                        raise SDDError("native command failed or is still running; reconcile before retry")
                    result = result.get("output", "")
                elif "result" in result:
                    result = result["result"]
                else:
                    return result
            else:
                return result
        raise SDDError("native response envelope is too deeply nested")

    @staticmethod
    def decode_task_id(result: Any) -> str | None:
        result = HermesBridge.decode_response(result)
        if isinstance(result, dict):
            task_id = result.get("task_id") or result.get("id")
            if isinstance(task_id, (str, int)) and not isinstance(task_id, bool):
                return str(task_id)
        return None
