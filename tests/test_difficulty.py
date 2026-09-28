import tempfile
import unittest
from pathlib import Path

from sdd_hermes import SDDService
from sdd_hermes.core import SDDError
from sdd_hermes.difficulty import DIMENSIONS, assess
from sdd_hermes.planning import build_plan


class DifficultyTests(unittest.TestCase):
    def test_low_requires_all_dimensions_known_low(self):
        self.assertEqual(assess()['tier'], 'med')
        self.assertEqual(assess({'scope': 'low'}, 'small scope')['tier'], 'med')
        self.assertEqual(assess(dict.fromkeys(DIMENSIONS, 'low'), 'bounded checklist')['tier'], 'low')

    def test_high_risk_is_never_averaged_away(self):
        dimensions = dict.fromkeys(DIMENSIONS, 'low')
        dimensions['consequence'] = 'high'
        self.assertEqual(assess(dimensions, 'permission migration')['tier'], 'high')
        with self.assertRaises(SDDError):
            assess(dimensions, 'hide risk', 'low')

    def test_medium_alias_and_override_rationale(self):
        self.assertEqual(assess({'scope': 'medium'}, 'bounded changes')['tier'], 'med')
        with self.assertRaises(SDDError):
            assess(override='high')
        self.assertEqual(assess(override='high', rationale='uncertain architecture')['tier'], 'high')

    def test_difficulty_is_independent_of_request_workflow(self):
        high = {'T-001': {'dimensions': {'consequence': 'high'}, 'rationale': 'critical data repair'}}
        low = {'T-001': {'dimensions': dict.fromkeys(DIMENSIONS, 'low'), 'rationale': 'known checklist'}}
        self.assertEqual(build_plan('Fix typo', 'bugfix', high).tasks[0]['difficulty']['tier'], 'high')
        self.assertEqual(build_plan('new product', 'product', low).tasks[0]['difficulty']['tier'], 'low')

    def test_assessment_persists_and_cannot_be_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = SDDService(root)
            assessment = {'T-001': {'override': 'high', 'rationale': 'cross component uncertainty'}}
            service.initialize('Fix regression', 'bugfix', task_assessments=assessment)
            restarted = SDDService(root)
            self.assertEqual(restarted.status()['tasks'][0]['difficulty']['tier'], 'high')
            self.assertFalse(restarted.status()['routing']['escalation_available'])
            with self.assertRaises(SDDError):
                restarted.initialize('Fix regression', 'bugfix')
