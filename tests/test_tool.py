import csv
import io
import tempfile
import unittest
from pathlib import Path

from tool import CSV_COLUMNS, FEATURES, ROOT, create_app, parse_csv, select_discharges
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


class DischargeSelectionTests(unittest.TestCase):
    def test_boundary_tie_is_entirely_reviewed_not_lexically_selected(self):
        result = select_discharges(
            ["SYNTH-D", "SYNTH-C", "SYNTH-A", "SYNTH-B"],
            [0.1, 0.5, 0.9, 0.5], capacity=2, minutes_per_contact=30,
        )
        self.assertEqual(
            [(row["discharge_reference"], row["selected"], row["review"]) for row in result["rows"]],
            [("SYNTH-A", True, False), ("SYNTH-B", False, True),
             ("SYNTH-C", False, True), ("SYNTH-D", False, False)],
        )
        self.assertEqual(result["summary"]["remaining_capacity"], 1)
        self.assertEqual(result["summary"]["review"], 2)
        self.assertEqual(result["summary"]["staff_hours"], 0.5)
        self.assertEqual(result["summary"]["boundary_risk"], 0.5)

    def test_zero_and_excess_capacity_do_not_create_tie_reviews(self):
        for capacity, selected, remaining, boundary in [(0, 0, 0, None), (2, 2, 0, 0.4), (5, 2, 3, 0.4)]:
            with self.subTest(capacity=capacity):
                result = select_discharges(["SYNTH-A", "SYNTH-B"], [0.4, 0.4], capacity, 60)
                self.assertEqual(result["summary"]["selected"], selected)
                self.assertEqual(result["summary"]["review"], 0)
                self.assertEqual(result["summary"]["remaining_capacity"], remaining)
                self.assertEqual(result["summary"]["staff_hours"], selected)
                self.assertEqual(result["summary"]["boundary_risk"], boundary)


class CsvValidationTests(unittest.TestCase):
    def setUp(self):
        self.row = next(csv.DictReader(io.StringIO((ROOT / "examples/discharge_example.csv").read_text())))
        # A schema-only parser fixture; scoring tests never substitute a model.
        self.categories = {name: {self.row[name]} for name in
                           ("age", "race", "gender", "admission_type_id", "admission_source_id",
                            "A1Cresult", "insulin", "change", "diabetesMed")}

    def csv_bytes(self, rows, columns=CSV_COLUMNS):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
        return stream.getvalue().encode("utf-8")

    def test_rejects_unsafe_references_and_unexpected_or_duplicate_columns(self):
        for reference in ("=PRIVATE()", "+PRIVATE", "-PRIVATE", "@PRIVATE", "", "PRIVATE NAME"):
            with self.subTest(reference=reference):
                row = {**self.row, "discharge_reference": reference}
                with self.assertRaises(ValueError) as error:
                    parse_csv(self.csv_bytes([row]), FEATURES, self.categories)
                self.assertNotIn("PRIVATE", str(error.exception))
        for columns, row in [
            (CSV_COLUMNS + ("readmitted",), {**self.row, "readmitted": "PRIVATE"}),
            (CSV_COLUMNS + ("discharge_reference",), self.row),
        ]:
            with self.subTest(columns=columns):
                with self.assertRaises(ValueError) as error:
                    parse_csv(self.csv_bytes([row], columns), FEATURES, self.categories)
                self.assertNotIn("PRIVATE", str(error.exception))
        with self.assertRaises(ValueError):
            parse_csv(self.csv_bytes([self.row, self.row]), FEATURES, self.categories)

    def test_preserves_literal_none_and_allows_only_race_missingness(self):
        raw = self.csv_bytes([{**self.row, "race": "?"}], tuple(reversed(CSV_COLUMNS)))
        references, frame, missing_race = parse_csv(b"\xef\xbb\xbf" + raw, FEATURES, self.categories)
        self.assertEqual(references, [self.row["discharge_reference"]])
        self.assertEqual(frame.loc[0, "A1Cresult"], "None")
        self.assertTrue(frame["race"].isna().all())
        self.assertTrue(missing_race)
        for name, value in [
            ("time_in_hospital", "0"), ("num_medications", "nan"),
            ("num_procedures", "1.5"), ("race", "unsupported"),
            ("age", "[10-20)"), ("gender", "Unknown/Invalid"),
            ("admission_type_id", "1.0"), ("A1Cresult", ""),
        ]:
            with self.subTest(column=name):
                with self.assertRaises(ValueError):
                    parse_csv(self.csv_bytes([{**self.row, name: value}]), FEATURES, self.categories)


class CsvRequestSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.artifacts = Path(self.directory.name)
        self.client = create_app(self.artifacts).test_client()
        self.url = "/api/score?capacity=2&minutes_per_contact=20&eligible=true"
        self.body = (ROOT / "examples/discharge_example.csv").read_bytes()

    def test_missing_or_corrupt_artifact_fails_closed_without_upload_storage(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt):
                if corrupt:
                    (self.artifacts / "calibrated_logistic.joblib").write_bytes(b"invalid artifact")
                before = set(self.artifacts.iterdir())
                response = self.client.post(self.url, data=self.body, content_type="text/csv")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(set(response.get_json()), {"error"})
                self.assertNotIn("SYNTH-", response.get_data(as_text=True))
                self.assertEqual(set(self.artifacts.iterdir()), before)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertNotIn("Set-Cookie", response.headers)
                self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_cross_origin_and_oversized_uploads_are_rejected_before_scoring(self):
        for headers in ({"Origin": "https://example.com"}, {"Sec-Fetch-Site": "cross-site"}):
            with self.subTest(headers=headers):
                response = self.client.post(self.url, data=self.body, content_type="text/csv", headers=headers)
                self.assertEqual(response.status_code, 400)
        response = self.client.post(self.url, data=b"x" * (2 * 1024 * 1024 + 1), content_type="text/csv")
        self.assertEqual(response.status_code, 413)
        self.assertEqual(set(response.get_json()), {"error"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
