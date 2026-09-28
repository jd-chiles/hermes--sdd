import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sdd_hermes import SDDService
from sdd_hermes.core import SDDError


class RequestLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()

    def test_ten_requests_with_repeated_titles_keep_identity_and_artifacts(self):
        identities, boards, specs = set(), set(), {}
        for _ in range(10):
            service = SDDService(self.root)
            result = service.initialize('Fix repeated regression', 'bugfix')
            identity = result['project']['project_id']
            self.assertNotIn(identity, identities)
            identities.add(identity)
            self.assertNotIn(result['project']['board_slug'], boards)
            boards.add(result['project']['board_slug'])
            path = Path(result['spec_path'])
            self.assertNotIn(path, specs)
            specs[path] = path.read_bytes()
            # This fixture isolates identity/archiving from acceptance evaluation.
            service.ledger.set_stage('accepted')
            self.assertFalse(service.close()['idempotent'])
            self.assertTrue(SDDService(self.root).close()['idempotent'])
        self.assertEqual(len(identities), 10)
        for path, content in specs.items():
            self.assertEqual(path.read_bytes(), content)
        with service.ledger._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM projects').fetchone()[0], 10)

    def test_second_request_replay_keeps_stage_and_spec(self):
        service = SDDService(self.root)
        service.initialize('Fix first regression', 'bugfix')
        service.ledger.set_stage('accepted')
        service.close()
        result = service.initialize('Fix second regression', 'bugfix')
        path = Path(result['spec_path'])
        path.write_text(path.read_text() + '\nPreserved operator note.\n')
        original = path.read_bytes()
        service.pause()
        replay = SDDService(self.root).initialize('Fix second regression', 'bugfix')
        self.assertEqual(replay['project']['project_id'], result['project']['project_id'])
        self.assertEqual(replay['project']['stage'], 'paused')
        self.assertTrue(replay['project']['paused'])
        self.assertEqual(path.read_bytes(), original)

    def test_replay_rejects_changed_limits(self):
        service = SDDService(self.root)
        service.initialize('Fix regression', limits={'max_workers': 1})
        with self.assertRaises(SDDError):
            service.initialize('Fix regression', limits={'max_workers': 2})

    def test_concurrent_initialization_has_one_active_request(self):
        services = [SDDService(self.root), SDDService(self.root)]
        barrier = threading.Barrier(2)
        def initialize(index):
            barrier.wait()
            return services[index].initialize('Fix concurrent regression')['project']['project_id']
        with ThreadPoolExecutor(2) as executor:
            identities = list(executor.map(initialize, range(2)))
        self.assertEqual(len(set(identities)), 1)
        events = [json.loads(line) for line in services[0].paths.jsonl.read_text().splitlines()]
        self.assertEqual(sum(e['event_type'] == 'project_initialized' for e in events), 1)

