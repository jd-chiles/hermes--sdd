#!/usr/bin/env python3
"""Build a source-only Hermes plugin artifact with a deterministic file set."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path


EXCLUDED_PARTS = {".git", ".sdd", "__pycache__", ".pytest_cache"}
EXCLUDED_NAMES = {".DS_Store"}


def files_for(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts) or path.name in EXCLUDED_NAMES or path.suffix == ".pyc":
            continue
        result.append(path)
    return result


def build(root: Path, output: Path) -> dict[str, object]:
    output.parent.mkdir(parents=True, exist_ok=True)
    files = files_for(root)
    with tarfile.open(output, "w:gz") as archive:
        for path in files:
            relative = path.relative_to(root)
            info = archive.gettarinfo(str(path), arcname=str(relative))
            info.mtime = 0
            with path.open("rb") as stream:
                archive.addfile(info, stream)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = {"artifact": str(output), "sha256": digest, "files": [str(path.relative_to(root)) for path in files]}
    output.with_suffix(output.suffix + ".json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "dist" / "hermes-sdd-team-0.1.0.tar.gz").resolve()
    print(json.dumps(build(root, output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
