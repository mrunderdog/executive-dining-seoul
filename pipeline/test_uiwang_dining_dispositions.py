"""Exact row-ID recommendation disposition guard for Uiwang source replay."""
import copy
import json
import unittest
from pathlib import Path

from replay_failed_uiwang_pdfs import apply_dining_dispositions

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "pipeline/uiwang_2026_q3_dining_dispositions.json").read_text(encoding="utf-8"))


class DispositionTests(unittest.TestCase):
    def make_rows(self):
        return [
            {"row_id": d["row_id"], "merchant": d["merchant"], "amount": d["amount_krw"],
             "source_period": [2026, 7, None], "source_row": i + 1,
             "source_sheet": "pdf-page-1"}
            for i, d in enumerate(POLICY["dispositions"])
        ]

    def test_exact_dispositions_partition_without_mutation(self):
        rows = self.make_rows()
        rows.append({"row_id": "safe-other-row", "merchant": "구이마을", "amount": 55000})
        original = copy.deepcopy(rows)
        r = apply_dining_dispositions(rows, POLICY)
        self.assertEqual(r["status"], "PASS", r)
        self.assertEqual(r["excluded_non_dining"], 13)
        self.assertEqual(r["held_multi_merchant"], 4)
        self.assertEqual(r["remaining_candidate_rows"], 1)
        self.assertEqual(r["remaining_candidates"][0]["row_id"], "safe-other-row")
        self.assertEqual(rows, original)
        self.assertFalse(r["publish"])

    def test_changed_merchant_or_amount_is_hold(self):
        rows = self.make_rows()
        rows[0]["amount"] += 100
        r = apply_dining_dispositions(rows, POLICY)
        self.assertEqual(r["status"], "HOLD")
        self.assertIn("disposition_source_content_mismatch", r["failures"])

    def test_missing_flagged_record_is_hold(self):
        rows = self.make_rows()[1:]
        r = apply_dining_dispositions(rows, POLICY)
        self.assertEqual(r["status"], "HOLD")
        self.assertIn("disposition_not_in_replay", r["failures"])

    def test_unknown_decision_and_duplicate_held(self):
        rows = self.make_rows()
        bad = copy.deepcopy(POLICY)
        bad["dispositions"][0]["disposition"] = "PUBLISH"
        self.assertIn("unknown_dining_disposition",
                      apply_dining_dispositions(rows, bad)["failures"])
        dup = copy.deepcopy(POLICY)
        dup["dispositions"].append(dup["dispositions"][0])
        self.assertIn("duplicate_dining_disposition",
                      apply_dining_dispositions(rows, dup)["failures"])


if __name__ == "__main__":
    unittest.main()
