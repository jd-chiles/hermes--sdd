import argparse
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from sdd_hermes import SDDService, _cli_handler, _slash
from sdd_hermes.core import SDDError


class CommandTests(unittest.TestCase):
    def test_slash_fix_requests_execution(self):
        with patch('sdd_hermes._handle_tool', return_value='ok') as handle:
            _slash(object(), 'fix parser regression')
        self.assertTrue(handle.call_args.args[2]['execute'])
        self.assertEqual(handle.call_args.args[2]['mode'], 'bugfix')

    def test_cli_without_subcommand_shows_status(self):
        with tempfile.TemporaryDirectory() as directory:
            args = argparse.Namespace(project_root=directory, sdd_command=None)
            output = StringIO()
            with redirect_stdout(output):
                _cli_handler(args)
            self.assertFalse(json.loads(output.getvalue())['initialized'])

    def test_execute_without_dispatch_preserves_plan_and_reports_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            service = SDDService(Path(directory))
            with self.assertRaisesRegex(SDDError, 'dispatch context is unavailable'):
                service.initialize('Fix regression', 'bugfix', execute=True)
            self.assertEqual(service.status()['project']['stage'], 'planned')
            self.assertTrue(all(t['native_task_id'] is None for t in service.ledger.tasks()))
