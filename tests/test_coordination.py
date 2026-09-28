import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sdd_hermes import SDDService
from sdd_hermes.bridge import HermesBridge
from sdd_hermes.core import SDDError
from sdd_hermes.planning import build_plan


class CoordinationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.service = SDDService(self.root)
        self.service.initialize('Fix regression', 'bugfix')

    def race(self, operation):
        barrier = threading.Barrier(2)
        def run(index):
            service = SDDService(self.root)
            barrier.wait()
            try:
                return operation(service, index)
            except SDDError:
                return False
        with ThreadPoolExecutor(2) as executor:
            return list(executor.map(run, range(2)))

    def test_concurrent_lease_has_one_winner(self):
        self.assertEqual(self.race(lambda s, i: s.ledger.acquire_lease(str(i))).count(True), 1)

    def test_concurrent_overlapping_ownership_has_one_winner(self):
        tasks = self.service.ledger.tasks()
        def claim(service, index):
            service.admit(tasks[index]['task_id'], ['src' if index else 'src/app.py'], f'claim-{index}')
            return True
        self.assertEqual(self.race(claim).count(True), 1)

    def test_operation_replay_with_changed_payload_is_rejected_before_mutation(self):
        task = self.service.ledger.tasks()[0]['task_id']
        self.service.admit(task, ['a.py'], 'same-op')
        self.service.admit(task, ['a.py'], 'same-op')
        with self.assertRaises(SDDError):
            self.service.admit(task, ['b.py'], 'same-op')
        self.assertEqual([x['path'] for x in self.service.status()['ownership']], ['a.py'])

    def test_jsonl_rebuild_after_interrupted_export(self):
        self.service.paths.jsonl.write_text('partial')
        path = self.service.ledger.export_jsonl()
        events = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['event_type'], 'project_initialized')

    def test_fresh_and_paused_recovery_do_not_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(SDDService(Path(directory)).recover()['recovered'])
        self.service.pause()
        self.assertFalse(self.service.recover()['recovered'])
        with self.assertRaises(SDDError):
            self.service.admit(self.service.ledger.tasks()[0]['task_id'], ['a.py'], 'paused')

    def test_product_implementation_depends_on_ux_and_architecture(self):
        plan = build_plan('new product', 'product')
        self.assertEqual(plan.tasks[3]['parent_keys'], ['T-002', 'T-003'])

    def test_dispatch_intent_is_idempotent_and_lease_can_be_renewed(self):
        task = self.service.ledger.tasks()[0]
        first = self.service.ledger.dispatch_intent(task['task_id'], task['stable_key'], 'dispatch-1', {'parents': []}, {'provider': 'p', 'model': 'm'})
        second = self.service.ledger.dispatch_intent(task['task_id'], task['stable_key'], 'dispatch-1', {'parents': []}, {'provider': 'p', 'model': 'm'})
        self.assertEqual(first['operation_id'], second['operation_id'])
        self.assertFalse(first['replayed'])
        self.assertTrue(second['replayed'])
        with self.assertRaises(SDDError):
            self.service.ledger.dispatch_intent(task['task_id'], task['stable_key'], 'dispatch-1', {'parents': ['changed']}, {'provider': 'p', 'model': 'm'})
        self.assertTrue(self.service.ledger.acquire_lease('holder'))
        self.assertTrue(self.service.ledger.renew_lease('holder'))
        self.assertFalse(self.service.ledger.renew_lease('other'))

    def test_failure_recovery_is_durable_and_does_not_change_task_tier(self):
        task = self.service.ledger.tasks()[0]
        result = self.service.record_failure(task['task_id'], '429', route_identity='provider/model@default')
        self.assertEqual(result['failure']['class'], 'provider_transient')
        self.assertEqual(result['decision']['state'], 'waiting_provider')
        self.assertEqual(self.service.status()['recovery_events'][0]['failure_class'], 'provider_transient')

    def test_provider_cooldown_blocks_sibling_recovery_without_spending_budget(self):
        task = self.service.ledger.tasks()[0]
        self.service.record_failure(task['task_id'], '429', route_identity='provider/model@default')
        blocked = self.service.admit_recovery(task['task_id'], 'provider_transient', 'provider/model@default', 'distinct_effective_route')
        self.assertFalse(blocked['allowed'])
        self.assertEqual(blocked['state'], 'waiting_provider')
        self.assertEqual(self.service.status()['budgets'], [])
        restarted = SDDService(self.root)
        self.assertEqual(restarted.status()['route_breakers'][0]['route_identity'], 'provider/model@default')

    def test_expired_breaker_allows_one_half_open_probe(self):
        task = self.service.ledger.tasks()[0]
        self.service.record_failure(task['task_id'], '429', route_identity='provider/model@default', retry_after=0)
        first = self.service.admit_recovery(task['task_id'], 'provider_transient', 'provider/model@default', 'health_signal')
        second = self.service.admit_recovery(task['task_id'], 'provider_transient', 'provider/model@default', 'health_signal')
        self.assertTrue(first['allowed'])
        self.assertFalse(second['allowed'])
        self.assertEqual(second['reason'], 'half-open provider probe already claimed')

    def test_recovery_budgets_are_distinct_and_durable(self):
        task = self.service.ledger.tasks()[0]
        first = self.service.admit_recovery(task['task_id'], 'task_defect', 'provider/model@default', 'changed_repair_plan')
        second = self.service.admit_recovery(task['task_id'], 'task_defect', 'provider/model@default', 'changed_repair_plan')
        third = self.service.admit_recovery(task['task_id'], 'task_defect', 'provider/model@default', 'changed_repair_plan')
        self.assertTrue(first['allowed'] and second['allowed'])
        self.assertFalse(third['allowed'])
        self.assertEqual(third['reason'], 'repair budget exhausted')
        self.assertEqual(SDDService(self.root).status()['budgets'][0]['repair_cycles'], 2)

    def test_effective_route_receipt_is_persisted_on_dispatch_completion(self):
        task = self.service.ledger.tasks()[0]
        self.service.ledger.dispatch_intent(task['task_id'], task['stable_key'], 'dispatch-receipt', {'parents': []}, {'provider': 'p', 'model': 'requested'})
        self.service.ledger.complete_dispatch('dispatch-receipt', 'native-1', {'provider': 'p', 'model': 'effective'})
        row = self.service.status()['dispatches'][0]
        self.assertEqual(json.loads(row['effective_route_json'])['model'], 'effective')
        self.assertEqual(self.service.status()['budgets'][0]['native_launches'], 1)

    def test_recover_task_admits_budget_before_promoting_native_task(self):
        commands = []
        service = SDDService(self.root, HermesBridge(lambda name, args: commands.append(args['command']) or {'exit_code': 0, 'output': '{}'}))
        task = service.ledger.tasks()[0]
        service.ledger.set_native_task_id(task['task_id'], 'native-1')
        result = service.recover_task(task['task_id'], 'task_defect', 'provider/model@default', 'changed repair plan')
        self.assertTrue(result['admitted'])
        self.assertIn('promote native-1', commands[0])
        self.assertEqual(service.status()['budgets'][0]['repair_cycles'], 1)


class BridgeTests(unittest.TestCase):
    def test_create_task_propagates_native_idempotency_and_retry_controls(self):
        commands = []
        bridge = HermesBridge(lambda name, args: commands.append(args['command']) or {'exit_code': 0, 'output': json.dumps({'id': 'native-1'})})
        bridge.create_task('board', 'title', 'body', 'engineer', idempotency_key='op-1', max_retries=3)
        self.assertIn('--idempotency-key op-1', commands[0])
        self.assertIn('--max-retries 3', commands[0])

    def test_terminal_envelope_and_numeric_task_id(self):
        result = json.dumps({'exit_code': 0, 'output': json.dumps({'id': 240})})
        self.assertEqual(HermesBridge.decode_task_id(result), '240')
        for raw in ({'exit_code': 1, 'output': '{}'}, {'exit_code': None, 'output': '{}'}, 'not json'):
            with self.assertRaises(SDDError):
                HermesBridge.decode_task_id(raw)

    def test_exact_marker_and_direct_lists(self):
        tasks = [{'id': 'wrong', 'body': 'Depends on T-001\nStable task: T-0010'}, {'id': 'right', 'body': 'Stable task: T-001'}]
        bridge = HermesBridge(lambda name, args: tasks)
        self.assertEqual(bridge.find_task('board', 'T-001'), 'right')
        tasks.append({'id': 'duplicate', 'body': 'Stable task: T-001'})
        with self.assertRaises(SDDError):
            bridge.find_task('board', 'T-001')

    def test_missing_parent_creation_receipt_stops_child_dispatch(self):
        class FailedBridge(HermesBridge):
            def __init__(self):
                super().__init__(lambda *args: None)
                self.created = []
            def provision_profiles(self, profiles):
                return []
            def ensure_board(self, *args):
                return {}
            def find_task(self, *args):
                return None
            def create_task(self, board, title, body, assignee, parents):
                self.created.append(title)
                return {'result': {}}
        with tempfile.TemporaryDirectory() as directory:
            bridge = FailedBridge()
            service = SDDService(Path(directory), bridge)
            with self.assertRaises(SDDError):
                service.initialize('Fix regression', 'bugfix', execute=True)
            self.assertEqual(len(bridge.created), 1)

    def test_effective_route_receipt_is_optional_and_explicit(self):
        self.assertEqual(HermesBridge.effective_route({'effective_route': {'provider': 'p', 'model': 'm'}})['model'], 'm')
        self.assertIsNone(HermesBridge.effective_route({'id': 'native-1'}))
        self.assertEqual(HermesBridge.retry_after_seconds({'headers': {'Retry-After': '12'}}), 12)
        self.assertIsNone(HermesBridge.retry_after_seconds({'message': 'try later'}))

    def test_promote_task_uses_native_recovery_command(self):
        commands = []
        bridge = HermesBridge(lambda name, args: commands.append(args['command']) or {'exit_code': 0, 'output': '{}'})
        bridge.promote_task('board', 'native-1', 'changed route')
        self.assertIn('promote native-1', commands[0])
        self.assertIn('--json', commands[0])
