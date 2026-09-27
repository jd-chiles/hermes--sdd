#!/usr/bin/env python3
"""Verify a pinned plugin install preserves unrelated profile configuration."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def run(command: list[str], env: dict[str, str]) -> dict[str, object]:
    completed = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    return {"command": command, "exit_status": completed.returncode, "stdout": completed.stdout[-8000:], "stderr": completed.stderr[-8000:]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--ref", required=True)
    args = parser.parse_args()
    if len(args.ref) != 40 or any(character not in "0123456789abcdef" for character in args.ref.lower()):
        parser.error("--ref must be a full 40-character hexadecimal commit SHA")
    hermes = shutil.which("hermes")
    if not hermes:
        print(json.dumps({"ok": False, "blocked": "hermes executable is not on PATH"}, indent=2))
        return 2
    directory = Path(tempfile.mkdtemp(prefix="hermes-sdd-profile-preservation-"))
    home = directory / "hermes-home"
    home.mkdir()
    top_level_soul = home / "SOUL.md"
    top_level_soul.write_text("user-owned top-level sentinel\n", encoding="utf-8")
    profile_soul = home / "profiles" / "untouched" / "SOUL.md"
    profile_soul.parent.mkdir(parents=True)
    profile_soul.write_text("user-owned untouched-profile sentinel\n", encoding="utf-8")
    before_top = top_level_soul.read_bytes()
    before_profile = profile_soul.read_bytes()
    env = {**os.environ, "HERMES_HOME": str(home)}
    install = run([hermes, "plugins", "install", args.repo, "--ref", args.ref, "--enable"], env)
    preserved = top_level_soul.read_bytes() == before_top and profile_soul.read_bytes() == before_profile
    listing = run([hermes, "plugins", "list", "--plain", "--no-bundled"], env)
    enabled = any(line.startswith("enabled ") and "hermes-sdd-team" in line for line in str(listing["stdout"]).splitlines())
    result = {"ok": install["exit_status"] == 0 and listing["exit_status"] == 0 and enabled and preserved, "enabled": enabled, "preserved": preserved, "isolated_home": str(home), "checks": [install, listing]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
