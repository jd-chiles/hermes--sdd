#!/usr/bin/env python3
"""Inventory pinned host source and probe CLI startup without launching workers.

This is discovery evidence, not lifecycle certification. Even a successful help
probe leaves native receipt/deadline semantics unverified.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def inventory(root: Path, expected_revision: str, executable: str | None = None) -> dict:
    root = root.resolve()
    revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True, timeout=10).strip()
    if revision != expected_revision:
        raise ValueError(f'host revision mismatch: expected {expected_revision}, found {revision}')
    dirty = bool(subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'], text=True, timeout=10).strip())
    source_path = root / 'hermes_cli/kanban_parser.py'
    source = source_path.read_bytes()
    tree = ast.parse(source)
    commands = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '_cmd' and node.args and isinstance(node.args[0], ast.Constant):
            commands[node.args[0].value] = sorted({item.value for item in ast.walk(node) if isinstance(item, ast.Constant) and isinstance(item.value, str) and item.value.startswith('--') and ' ' not in item.value})
    expected = {
        'task_creation': ('create', ['--idempotency-key', '--initial-status']),
        'attempt_receipts': ('runs', []),
        'task_inspection': ('show', []),
        'interruption': ('block', []),
        'promotion': ('promote', []),
        'review_transition': ('request-review', []),
        'runtime_deadline': ('create', ['--max-runtime']),
    }
    capabilities = {name: {
        'state': 'unverified', 'command': command,
        'source_declared': command in commands and set(flags) <= set(commands[command]),
        'required_flags': flags,
        'reason': 'source declarations do not verify runtime semantics or receipts',
    } for name, (command, flags) in expected.items()}
    probe = {'state': 'blocked', 'reason': 'hermes executable not found'}
    executable = executable or shutil.which('hermes')
    if executable:
        with tempfile.TemporaryDirectory(prefix='sdd-host-contract-') as directory:
            env = {**os.environ, 'HERMES_HOME': directory}
            env.pop('HERMES_PROFILE', None)
            try:
                result = subprocess.run([executable, 'kanban', 'create', '--help'], env=env, cwd=directory,
                                        capture_output=True, text=True, timeout=30)
                # Do not store arbitrary host output/environment in the report.
                missing = 'ruamel.yaml dependency is unavailable' if "No module named 'ruamel'" in result.stderr else 'host CLI startup failed; inspect it in an isolated home'
                probe = {'state': 'passed' if result.returncode == 0 else 'blocked',
                         'exit_status': result.returncode,
                         'reason': 'help command succeeded; lifecycle semantics remain unverified' if result.returncode == 0 else missing}
            except (OSError, subprocess.TimeoutExpired) as exc:
                probe = {'state': 'blocked', 'reason': type(exc).__name__}
    return {'host_revision': revision, 'source_dirty': dirty,
            'parser_sha256': hashlib.sha256(source).hexdigest(),
            'cli_startup': probe, 'capabilities': capabilities,
            'certified': False, 'worker_launched': False,
            'executable_checkout_binding': 'unverified',
            'next_action': 'repair host startup if blocked, then collect real isolated lifecycle receipts against this revision'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-root', type=Path, required=True)
    parser.add_argument('--expected-revision', required=True)
    parser.add_argument('--hermes-executable')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = inventory(args.host_root, args.expected_revision, args.hermes_executable)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, f'Host inventory failed: {exc}\n')
    rendered = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end='')
    return 0 if result['cli_startup']['state'] == 'passed' and not result['source_dirty'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
