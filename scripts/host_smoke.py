#!/usr/bin/env python3
"""Validate the actual packaged artifact through Hermes' plugin checks."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from package_release import build


def run(command: list[str], cwd: Path) -> dict[str, object]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    return {"command": command, "exit_status": completed.returncode, "stdout": completed.stdout[-8000:], "stderr": completed.stderr[-8000:]}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    hermes = shutil.which("hermes")
    if not hermes:
        print(json.dumps({"ok": False, "blocked": "hermes executable is not on PATH"}, indent=2))
        return 2
    with tempfile.TemporaryDirectory(prefix="hermes-sdd-release-") as directory:
        workspace = Path(directory)
        artifact = workspace / "hermes-sdd.tar.gz"
        build(root, artifact)
        extracted = workspace / "plugin"
        extracted.mkdir()
        import tarfile

        with tarfile.open(artifact) as archive:
            archive.extractall(extracted)
        checks = [
            run([hermes, "plugins", "doctor", str(extracted), "--ci"], root),
            run([hermes, "plugins", "validate", str(extracted)], root),
        ]
        result = {"ok": all(item["exit_status"] == 0 for item in checks), "artifact": str(artifact), "checks": checks}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
