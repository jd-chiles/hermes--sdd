import tempfile
import unittest
from pathlib import Path

from sdd_hermes import SDDService
from sdd_hermes.core import SDDError


class RuntimeAccountingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.service = SDDService(self.root)
        self.service.initialize('Fix budget regression', limits={
            'max_workers': 1, 'max_total_runtime_seconds': 10, 'max_runtime_seconds': 10,
        })
        self.tasks = self.service.ledger.tasks()

    def reserve(self, operation, seconds=10, index=0):
        return self.service.ledger.admit_capacity(self.tasks[index]['task_id'], operation, 'engineer', seconds)

    def test_completed_runtime_is_not_refunded_after_restart(self):
        self.assertTrue(self.reserve('one')['allowed'])
        self.service.complete_task('one', 10)
        self.service = SDDService(self.root)
        result = self.reserve('two', 1, index=1)
        self.assertFalse(result['allowed'])
        self.assertEqual(result['blocked'], 'total_runtime')
        self.assertEqual(result['usage'], 11)

    def test_failed_attempt_runtime_counts_towards_task_cap(self):
        self.assertTrue(self.reserve('one', 6)['allowed'])
        self.service.complete_task('one', 6, 'failed')
        result = self.reserve('two', 5)
        self.assertFalse(result['allowed'])
        self.assertEqual(result['blocked'], 'task_runtime')

    def test_ambiguous_completion_keeps_capacity_until_reconciled(self):
        self.reserve('one')
        self.service.complete_task('one', 3, 'ambiguous')
        self.assertFalse(self.reserve('two', 1, index=1)['allowed'])
        result = self.service.complete_task('one', 4)
        self.assertFalse(result['idempotent'])
        self.assertTrue(self.reserve('two', 6, index=1)['allowed'])

    def test_changed_payload_replay_and_conflicting_completion_rejected(self):
        self.reserve('one', 5)
        with self.assertRaises(SDDError):
            self.reserve('one', 4)
        with self.assertRaises(SDDError):
            self.reserve('one', 5, index=1)
        self.service.complete_task('one', 4)
        self.assertTrue(self.service.complete_task('one', 4)['idempotent'])
        with self.assertRaises(SDDError):
            self.service.complete_task('one', 0)

    def test_negative_runtime_is_not_silently_clamped(self):
        self.reserve('one')
        with self.assertRaises(SDDError):
            self.service.complete_task('one', -1)

    def test_overrun_blocks_next_task_and_leaves_budget_blocker_visible(self):
        self.reserve('one')
        self.assertFalse(self.reserve('two', 1, index=1)['allowed'])
        self.service.complete_task('one', 12)
        result = self.reserve('two', 1, index=1)
        self.assertFalse(result['allowed'])
        self.assertEqual(result['usage'], 13)
        self.assertTrue(any(b['limit_name'] == 'total_runtime' for b in self.service.ledger.blockers()))
