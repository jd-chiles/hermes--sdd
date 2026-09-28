"""Explicit known release blockers; unexpected success requires removing the marker.

These tests are not acceptance passes. S6-04 and S6-07/08 must turn them into
ordinary passing regressions before Sprint 6 can be accepted.
"""
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

from sdd_hermes import SDDService
from sdd_hermes.bridge import HermesBridge


class ReceiptBridge(HermesBridge):
    def __init__(self):
        super().__init__(lambda *args: None)
        self.created = []

    def provision_profiles(self, profiles):
        return []

    def ensure_board(self, *args):
        return {}

    def find_task(self, *args):
        return None

    def create_task(self, board, title, body, assignee, parents=None, **kwargs):
        self.created.append(title)
        return {'result': {'id': str(len(self.created))}}


class PendingSprint6Tests(unittest.TestCase):
    def test_feature_graph_only_reserves_capacity_for_runnable_work(self):
        with tempfile.TemporaryDirectory() as directory:
            service = SDDService(Path(directory), ReceiptBridge())
            service.initialize('Add a validation rule', 'feature', execute=True)
            self.assertEqual(len(service.ledger.tasks()), 5)
            self.assertEqual(len(service.ledger.capacity()), 1)

    def test_empty_submissions_and_noop_evidence_cannot_accept_implementation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = SDDService(root, actor='engineer')
            service.initialize('Fix missing validation', 'bugfix')
            engineer, reviewer, _ = service.ledger.tasks()
            attempt = service.submit(engineer['task_id'], 1, [], [], 'no implementation')
            command = shlex.join([sys.executable, '-c', 'pass'])
            for criterion in ('AC-001', 'AC-002'):
                service.verify(attempt['attempt_id'], criterion, command, [])
            SDDService(root, actor='reviewer').submit(reviewer['task_id'], 1, [], [], 'review')
            self.assertFalse(service.accept()['accepted'])

    def test_reviewer_verdict_is_structured_and_request_changes_blocks_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = SDDService(root, actor='reviewer')
            service.initialize('Fix missing validation', 'bugfix')
            reviewer = next(task for task in service.ledger.tasks() if task['role'] == 'reviewer')
            result = service.submit(reviewer['task_id'], 1, ['README.md'], ['python -m unittest'], 'needs changes', verdict='request_changes')
            self.assertTrue(result['attempt_id'])
            with service.ledger._connect() as db:
                verdict = db.execute('SELECT verdict FROM review_verdicts WHERE attempt_id = ?', (result['attempt_id'],)).fetchone()['verdict']
            self.assertEqual(verdict, 'request_changes')
