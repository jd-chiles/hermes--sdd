import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sdd_hermes import SDDService
from sdd_hermes.routing import classify_failure, recovery_decision, resolve_routes


class RoutingTests(unittest.TestCase):
    def test_missing_routes_are_unavailable_and_shared_routes_are_not_escalation(self):
        self.assertEqual(resolve_routes(None)['state'], 'unconfigured')
        config = {'tiers': {tier: {'provider': 'p', 'model': 'm'} for tier in ('low', 'med', 'high')}}
        result = resolve_routes(config)
        self.assertTrue(result['shared_route'])
        self.assertFalse(result['escalation_available'])

    def test_distinct_authorized_routes_enable_escalation(self):
        config = {'policy_version': '2026-09', 'tiers': {
            'low': {'provider': 'p', 'model': 'small'},
            'med': {'provider': 'p', 'model': 'medium'},
            'high': {'provider': 'p', 'model': 'large'},
        }}
        result = resolve_routes(config)
        self.assertTrue(result['escalation_available'])
        self.assertEqual(result['routes']['high']['model'], 'large')

    def test_failure_policy_requires_a_real_change(self):
        self.assertEqual(classify_failure('auth')['class'], 'provider_configuration')
        self.assertEqual(recovery_decision('provider_transient', 'p/small@default')['state'], 'waiting_provider')
        self.assertEqual(recovery_decision('provider_transient', 'p/small@default', 'p/large@default')['state'], 'repair_ready')
        self.assertEqual(recovery_decision('unknown_or_ambiguous', 'p/small@default')['state'], 'reconcile_required')

    def test_service_reports_configured_but_unverified_host_routing(self):
        config = {'tiers': {tier: {'provider': 'p', 'model': tier} for tier in ('low', 'med', 'high')}}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'HERMES_SDD_ROUTES_JSON': json.dumps(config)}):
            service = SDDService(Path(directory))
            service.initialize('Fix regression', 'bugfix')
            status = service.status()
            self.assertEqual(status['routing']['state'], 'configured')
            self.assertEqual(status['routing']['effective_host_routes'], 'unverified')
