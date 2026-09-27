import tempfile
import unittest
from pathlib import Path

from sdd_hermes.core import SDDError
from sdd_hermes.planning import build_plan
from sdd_hermes import SDDService


class SDDTests(unittest.TestCase):
    def test_adaptive_plan_sizes(self):
        self.assertEqual(len(build_plan("Fix the parser regression", "bugfix").tasks), 3)
        self.assertEqual(len(build_plan("Add a feature", "feature").tasks), 5)
        self.assertEqual(len(build_plan("Build a new product from scratch", "product").tasks), 7)

    def test_file_ownership_is_exclusive_and_paths_are_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = SDDService(root, actor="hermes-cli")
            service.initialize("Fix a regression", "bugfix")
            tasks = service.ledger.tasks()
            first, second = tasks[0]["task_id"], tasks[1]["task_id"]
            service.admit(first, ["src/parser.py"], "op-1")
            with self.assertRaises(SDDError):
                service.ledger.acquire_ownership(second, "reviewer", ["src/parser.py"], "op-2")
            with self.assertRaises(SDDError):
                service.ledger.acquire_ownership(second, "reviewer", ["../outside.py"], "op-3")

    def test_acceptance_requires_review_and_rejects_stale_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "app.py"
            source.write_text("value = 1\n", encoding="utf-8")
            engineer_service = SDDService(root, actor="engineer")
            engineer_service.initialize("Fix the app regression", "bugfix")
            engineer_task = next(t for t in engineer_service.ledger.tasks() if t["role"] == "engineer")["task_id"]
            reviewer_task = next(t for t in engineer_service.ledger.tasks() if t["role"] == "reviewer")["task_id"]
            engineer_attempt = engineer_service.submit(engineer_task, 1, ["app.py"], ["python3 -m unittest"], "Fixed the regression")
            engineer_service.verify(engineer_attempt["attempt_id"], "AC-001", "python3 -c 'assert True'", ["app.py"])
            engineer_service.verify(engineer_attempt["attempt_id"], "AC-002", "python3 -c 'assert True'", ["app.py"])
            before_review = engineer_service.accept()
            self.assertFalse(before_review["accepted"])
            self.assertIn("independent reviewer submission is missing", before_review["reasons"])

            reviewer_service = SDDService(root, actor="reviewer")
            reviewer_service.submit(reviewer_task, 1, ["app.py"], [], "Reviewed the change")
            self.assertTrue(engineer_service.accept()["accepted"])
            source.write_text("value = 2\n", encoding="utf-8")
            stale = engineer_service.accept()
            self.assertFalse(stale["accepted"])
            self.assertTrue(any("stale" in reason for reason in stale["reasons"]))

    def test_duplicate_attempt_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            service = SDDService(Path(directory), actor="engineer")
            service.initialize("Fix a regression", "bugfix")
            task_id = next(t for t in service.ledger.tasks() if t["role"] == "engineer")["task_id"]
            service.submit(task_id, 1, [], [], "first", attempt_id="attempt-1")
            with self.assertRaises(Exception):
                service.submit(task_id, 1, [], [], "duplicate", attempt_id="attempt-1")


if __name__ == "__main__":
    unittest.main()
