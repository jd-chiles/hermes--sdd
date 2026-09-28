#!/usr/bin/env python3
"""Build a source-only Hermes plugin artifact with a deterministic file set."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tarfile
from pathlib import Path


EXCLUDED_PARTS = {".git", ".sdd", "__pycache__", ".pytest_cache"}
EXCLUDED_NAMES = {".DS_Store"}
SOURCE_FILES = {"plugin.yaml", "__init__.py", "README.md", "LICENSE"}
SOURCE_DIRECTORIES = {"sdd_hermes", "skills", "profiles", "scripts", "tests", "docs"}


def files_for(root: Path, excluded: set[Path] | None = None) -> list[Path]:
    result: list[Path] = []
    excluded = excluded or set()

    def visit(path: Path) -> None:
        relative = path.relative_to(root)
        if path in excluded or any(part in EXCLUDED_PARTS or part.startswith(".") for part in relative.parts) or path.name in EXCLUDED_NAMES or path.suffix == ".pyc":
            return
        if path.is_symlink():
            raise ValueError(f"release sources must not be symlinks: {relative}")
        if path.is_dir():
            for child in sorted(path.iterdir()):
                visit(child)
        elif path.is_file():
            result.append(path)

    for name in sorted(SOURCE_FILES | SOURCE_DIRECTORIES):
        visit(root / name)
    return sorted(result)


def build(root: Path, output: Path) -> dict[str, object]:
    root = root.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = output.with_suffix(output.suffix + ".json")
    files = files_for(root, {output, manifest_path})
    with output.open("wb") as destination:
        with gzip.GzipFile(filename="", mode="wb", fileobj=destination, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in files:
                    info = tarfile.TarInfo(path.relative_to(root).as_posix())
                    info.size = path.stat().st_size
                    info.mode = 0o644
                    with path.open("rb") as stream:
                        archive.addfile(info, stream)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = {"artifact": str(output), "sha256": digest, "files": [path.relative_to(root).as_posix() for path in files]}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
