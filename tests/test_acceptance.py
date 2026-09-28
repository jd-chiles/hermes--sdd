import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sdd_hermes import SDDService
from sdd_hermes.core import SDDError


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'app.py').write_text('value = 1\n')
        self.service = SDDService(self.root, actor='engineer')
        self.service.initialize('Fix regression', 'bugfix')
        self.engineer, self.reviewer, self.qa = self.service.ledger.tasks()
        self.command = shlex.join([sys.executable, '-c', 'assert True'])

    def submit(self, task, actor, checks=()):
        return SDDService(self.root, actor=actor).submit(task['task_id'], 1, ['app.py'], list(checks), 'result')['attempt_id']

    def evidence(self, attempt):
        for criterion in ('AC-001', 'AC-002'):
            self.service.verify(attempt, criterion, self.command, ['app.py'])

    def accepted(self):
        attempt = self.submit(self.engineer, 'engineer', [self.command])
        self.evidence(attempt)
        self.submit(self.reviewer, 'reviewer')
        self.assertTrue(self.service.accept()['accepted'])
        return attempt

    def test_same_actor_cannot_review_own_submission(self):
        attempt = self.submit(self.engineer, 'hermes-cli')
        self.evidence(attempt)
        self.submit(self.reviewer, 'hermes-cli')
        self.assertFalse(self.service.accept()['accepted'])

    def test_required_commands_cannot_be_replaced_by_unrelated_evidence(self):
        attempt = self.submit(self.engineer, 'engineer', ['never executed'])
        self.evidence(attempt)
        self.submit(self.reviewer, 'reviewer')
        self.assertTrue(any('required command' in r for r in self.service.accept()['reasons']))

    def test_new_engineer_attempt_invalidates_review_evidence_and_stage(self):
        previous = self.accepted()
        self.submit(self.engineer, 'engineer')
        self.assertEqual(self.service.status()['project']['stage'], 'review')
        self.assertFalse(self.service.accept()['accepted'])
        with self.assertRaises(SDDError):
            self.evidence(previous)

    def test_file_change_invalidates_persisted_accepted_stage(self):
        self.accepted()
        (self.root / 'app.py').write_text('value = 2\n')
        self.assertFalse(self.service.accept()['accepted'])
        self.assertEqual(self.service.status()['project']['stage'], 'review')

    def test_scope_and_attempt_are_validated_before_command_runs(self):
        attempt = self.submit(self.engineer, 'engineer')
        with patch('sdd_hermes.core.subprocess.run') as run:
            for attempt_id, criterion, files in [(attempt, 'AC-001', []), ('unknown', 'AC-001', ['app.py']), (attempt, 'unknown', ['app.py'])]:
                with self.assertRaises(SDDError):
                    self.service.verify(attempt_id, criterion, self.command, files)
            run.assert_not_called()

    def test_review_before_engineer_is_not_current(self):
        self.submit(self.reviewer, 'reviewer')
        attempt = self.submit(self.engineer, 'engineer')
        self.evidence(attempt)
        self.assertFalse(self.service.accept()['accepted'])

    def test_latest_failed_check_is_not_hidden_by_earlier_success(self):
        attempt = self.accepted()
        with patch('sdd_hermes.core.subprocess.run') as run:
            run.return_value.returncode = 1
            run.return_value.stdout = ''
            run.return_value.stderr = 'failed'
            self.service.verify(attempt, 'AC-001', self.command, ['app.py'])
        self.assertFalse(self.service.accept()['accepted'])
        self.service.verify(attempt, 'AC-001', self.command, ['app.py'])
        self.assertTrue(self.service.accept()['accepted'])

    def test_verification_that_changes_files_cannot_accept(self):
        attempt = self.submit(self.engineer, 'engineer')
        command = shlex.join([sys.executable, '-c', "from pathlib import Path; Path('app.py').write_text('changed')"])
        result = self.service.verify(attempt, 'AC-001', command, ['app.py'])
        self.assertNotEqual(result['exit_status'], 0)
        self.assertFalse(self.service.accept()['accepted'])

    def test_legacy_attempt_without_context_requires_resubmission(self):
        self.accepted()
        with self.service.ledger._connect() as db:
            db.execute('DROP TRIGGER context_immutable_delete')
            db.execute('DELETE FROM attempt_context')
        self.assertFalse(SDDService(self.root).accept()['accepted'])
