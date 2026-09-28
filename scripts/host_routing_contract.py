#!/usr/bin/env python3
"""Check a pinned Hermes checkout's routing boundary without launching workers.

This is a source-contract check, not an authenticated provider smoke test.
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace


def check(root: Path) -> dict:
    revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    parser = (root / 'hermes_cli/kanban_parser.py').read_text()
    strings = {node.value for node in ast.walk(ast.parse(parser)) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    required = {'--model', '--provider', '--max-retries', '--json', '--idempotency-key'}
    if not required <= strings:
        raise RuntimeError(f'host is missing expected flags: {sorted(required - strings)}')
    source = ast.parse((root / 'hermes_cli/kanban_db_dispatch.py').read_text())
    function = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == '_worker_argv')
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), function], type_ignores=[])
    namespace = {'_resolve_hermes_argv': lambda: ['hermes'], '_resolve_worker_cli_toolsets': lambda home: []}
    exec(compile(ast.fix_missing_locations(module), str(root / 'hermes_cli/kanban_db_dispatch.py'), 'exec'), namespace)
    task = SimpleNamespace(id='contract-only', model_override='test-model', provider_override='test-provider', reasoning_effort=None, skills=())
    argv = namespace['_worker_argv'](task, 'reviewer', None)
    if argv[argv.index('-m') + 1] != 'test-model' or argv[argv.index('--provider') + 1] != 'test-provider':
        raise RuntimeError('host did not propagate model/provider overrides')
    task.model_override = None
    task.provider_override = None
    inherited = namespace['_worker_argv'](task, 'engineer', None)
    if '-m' in inherited or '--provider' in inherited:
        raise RuntimeError('host unexpectedly overrides inherited routing')
    return {'ok': True, 'host_revision': revision, 'checked': 'parser flags and actual worker argv builder',
            'worker_launched': False, 'effective_provider_verified': False, 'argv': argv}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.host_root), indent=2))
