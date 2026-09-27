#!/usr/bin/env python3
"""Install an exact Git revision in an isolated Hermes home and verify it."""

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
    return {"command": command, "exit_status": completed.returncode, "stdout": completed.stdout[-12000:], "stderr": completed.stderr[-12000:]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="GitHub owner/repository or Git URL")
    parser.add_argument("--ref", required=True, help="Full 40-character immutable commit SHA")
    args = parser.parse_args()
    if len(args.ref) != 40 or any(character not in "0123456789abcdef" for character in args.ref.lower()):
        parser.error("--ref must be a full 40-character hexadecimal commit SHA")
    hermes = shutil.which("hermes")
    if not hermes:
        print(json.dumps({"ok": False, "blocked": "hermes executable is not on PATH"}, indent=2))
        return 2
    directory = Path(tempfile.mkdtemp(prefix="hermes-sdd-clean-install-"))
    isolated_home = directory / "hermes-home"
    env = {**os.environ, "HERMES_HOME": str(isolated_home)}
    install = run([hermes, "plugins", "install", args.repo, "--ref", args.ref, "--enable"], env)
    listing = run([hermes, "plugins", "list", "--plain", "--no-bundled"], env)
    plugin_doctor = run([hermes, "plugins", "doctor", "hermes-sdd-team", "--ci"], env)
    listing_output = str(listing["stdout"])
    enabled = any(line.startswith("enabled ") and "hermes-sdd-team" in line for line in listing_output.splitlines())
    result = {"ok": all(item["exit_status"] == 0 for item in (install, listing, plugin_doctor)) and enabled, "enabled": enabled, "isolated_home": str(isolated_home), "repo": args.repo, "ref": args.ref, "checks": [install, listing, plugin_doctor]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
