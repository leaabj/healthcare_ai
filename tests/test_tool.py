import tempfile
import unittest
from pathlib import Path

from tool import create_app
from utils import threshold_table


class HospitalPlanningTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        artifacts = Path(self.directory.name)
        threshold_table([0, 1, 1, 0], [0.9, 0.8, 0.7, 0.1], 20).to_csv(
            artifacts / "policy_threshold_table.csv", index=False
        )
        self.client = create_app(artifacts).test_client()

    def test_infeasible_recall_does_not_override_contact_capacity(self):
        response = self.client.post("/api/plan", json={
            "discharges": 4, "capacity": 2, "recall_target": 100, "minutes_per_contact": 20,
        })

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertFalse(result["feasible"])
        self.assertEqual(result["maximum_recall"], 0.5)
        self.assertEqual(result["minimum_contacts_for_target"], 3)
        self.assertEqual(result["plan"]["contacts"], 2)
        self.assertEqual(result["plan"]["true_positives"], 1)
        self.assertEqual(result["plan"]["missed"], 1)

    def test_zero_capacity_reports_no_contacts_without_invalid_numbers(self):
        response = self.client.post("/api/plan", json={
            "discharges": 4, "capacity": 0, "recall_target": 0, "minutes_per_contact": 20,
        })

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["feasible"])
        self.assertEqual(result["plan"]["contacts"], 0)
        self.assertEqual(result["plan"]["staff_hours"], 0)
        self.assertEqual(result["plan"]["missed"], 2)
        self.assertIsNone(result["plan"]["threshold"])
        self.assertIsNone(result["plan"]["precision"])


if __name__ == "__main__":
    unittest.main()
