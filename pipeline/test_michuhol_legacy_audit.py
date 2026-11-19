import unittest
from copy import deepcopy

from apply_michuhol_legacy_audit import reconcile


class MichuholLegacyAuditTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "source_period": [2025, 4, None], "source_sheet": "chair.pdf::pdf-page-1",
            "source_row": 4, "used_date": "2025-04-02", "amount": 280000,
            "role": "의장", "merchant": "의원 및 직원 명7", "row_id": "legacy-stable-id",
            "source_post_url": "https://official.test/post",
            "source_attachment_url": "https://official.test/archive.zip",
            "source_key": "michuhol", "institution": "미추홀구의회",
            "purpose": "12:55", "used_time": "", "people": None,
        }
        self.raw = {
            "source": "michuhol", "row_count": 1, "rows": [deepcopy(self.original)],
            "files": [{"url": "https://official.test/archive.zip", "sha256": "f" * 64,
                       "sheets": [{"sheet": "chair.pdf::pdf-page-1", "parsed_rows": 1}]}],
            "raw_quality": {"rows": 1, "transaction_rows": 1},
        }
        repaired = {
            **{k: self.original[k] for k in ("source_sheet", "source_row", "used_date", "amount", "role")},
            "merchant": "스시진", "merchant_evidence": "official_pdf_usage_place_column",
            "row_id": "new-hash", "purpose": "직원 격려 간담회 식비", "people": 7,
            "payment_method": "카드", "used_time": "12:55",
        }
        added = {**repaired, "source_row": 5, "used_date": "2025-04-03",
                 "amount": 198000, "merchant": "소나무 디자인", "row_id": "new-id-2"}
        self.report = {
            "month": "2025-04", "status": "RECONCILED_WITH_ADDITIONS",
            "official_post": "https://official.test/post",
            "official_attachment": "https://official.test/archive.zip",
            "official_attachment_sha256": "f" * 64,
            "official_attachment_sha256_matches_committed": True,
            "legacy_rows": 1, "recovered_rows": 2,
            "unparsed_transaction_like_rows": 0, "bad_sheets": [],
            "unaccounted_legacy": [],
            "legacy": [deepcopy(self.original)],
            "recovered": [repaired, added],
            "sheets": [{"sheet": "chair.pdf::pdf-page-1", "status": "OK", "parsed_rows": 2,
                        "unparsed_transaction_like_rows": 0}],
        }

    def test_merchant_corrected_but_existing_id_stable_and_addition_kept(self):
        updated, result = reconcile(self.raw, self.report)
        self.assertEqual(result["merchant_corrections"], 1)
        self.assertEqual(result["new_rows"], 1)
        self.assertEqual(updated["row_count"], 2)
        self.assertEqual(updated["rows"][0]["row_id"], "legacy-stable-id")
        self.assertEqual(updated["rows"][0]["merchant"], "스시진")
        self.assertEqual(updated["rows"][1]["merchant"], "소나무 디자인")
        self.assertEqual(self.raw["rows"][0]["merchant"], "의원 및 직원 명7")

    def test_digest_mismatch_rejected(self):
        bad = deepcopy(self.report)
        bad["official_attachment_sha256"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "digest"):
            reconcile(self.raw, bad)

    def test_old_merchant_changed_rejected(self):
        bad = deepcopy(self.report)
        bad["legacy"][0]["merchant"] = "not-original"
        with self.assertRaisesRegex(ValueError, "Legacy proof"):
            reconcile(self.raw, bad)

    def test_missing_old_transaction_rejected(self):
        bad = deepcopy(self.report)
        bad["recovered"] = bad["recovered"][1:]
        bad["recovered_rows"] = 1
        with self.assertRaisesRegex(ValueError, "fully accounted"):
            reconcile(self.raw, bad)

    def test_unparsed_pdf_hold_rejected(self):
        bad = deepcopy(self.report)
        bad["unparsed_transaction_like_rows"] = 1
        with self.assertRaisesRegex(ValueError, "unresolved"):
            reconcile(self.raw, bad)


if __name__ == "__main__":
    unittest.main()
