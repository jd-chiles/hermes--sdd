"""Small adapter around Hermes-owned capabilities.

The adapter deliberately never writes Hermes' databases.  It uses the documented
tool dispatch boundary and explicit board arguments so the user's selected board
cannot accidentally receive this project's tasks.
"""

from __future__ import annotations

import json
import shlex
from typing import Any, Callable


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

    def create_task(self, board_slug: str, title: str, body: str, assignee: str, parents: list[str] | None = None) -> dict[str, Any]:
        if not self.dispatch:
            return {"available": False}
        command = f"hermes kanban --board {shlex.quote(board_slug)} create {shlex.quote(title)} --body {shlex.quote(body)} --assignee {shlex.quote(assignee)} --completion-contract local-only"
        for parent in parents or []:
            command += f" --parent {shlex.quote(parent)}"
        raw = self.terminal(command)
        return {"available": True, "result": raw}

    def find_task(self, board_slug: str, stable_key: str) -> str | None:
        """Find an already-created task during recovery using its stable body key."""
        if not self.dispatch:
            return None
        raw = self.terminal(f"hermes kanban --board {shlex.quote(board_slug)} list --json")
        if isinstance(raw, dict) and isinstance(raw.get("result"), (str, dict, list)):
            raw = raw["result"]
        candidates: list[Any] = []
        if isinstance(raw, dict):
            candidates = raw.get("tasks", raw.get("items", [])) if isinstance(raw.get("tasks", raw.get("items", [])), list) else []
        elif isinstance(raw, str):
            try:
                decoded = json.loads(raw)
                candidates = decoded if isinstance(decoded, list) else decoded.get("tasks", decoded.get("items", []))
            except (json.JSONDecodeError, AttributeError):
                return None
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            body = str(candidate.get("body", ""))
            if stable_key in body or candidate.get("stable_key") == stable_key:
                return candidate.get("task_id") or candidate.get("id")
        return None

    def transition_task(self, board_slug: str, native_task_id: str, action: str, reason: str = "") -> Any:
        if action not in {"block", "unblock"}:
            raise ValueError(f"unsupported Kanban transition: {action}")
        if not self.dispatch:
            return {"available": False}
        command = f"hermes kanban --board {shlex.quote(board_slug)} {action} {shlex.quote(native_task_id)}"
        if action == "block":
            command += f" {shlex.quote(reason or 'SDD pause requested')}"
        return self.terminal(command)

    @staticmethod
    def decode_task_id(result: Any) -> str | None:
        if isinstance(result, dict):
            return result.get("task_id") or result.get("id")
        if isinstance(result, str):
            try:
                decoded = json.loads(result)
                if isinstance(decoded, dict):
                    return decoded.get("task_id") or decoded.get("id")
            except json.JSONDecodeError:
                return None
        return None
