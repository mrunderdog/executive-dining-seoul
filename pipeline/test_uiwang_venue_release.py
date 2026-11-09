"""Source-preserving restaurant ranking preflight safeguards for Uiwang."""
import copy
import unittest
from audit_uiwang_venue_release import observed_time, suspected_alias_groups, assess_venues


class UiwangVenueReleaseTests(unittest.TestCase):
    def test_printed_time_and_missing_time_are_not_inferred(self):
        self.assertEqual(observed_time({"used_time": "13:38"}), "13:38")
        self.assertEqual(observed_time({"used_time": "2026. 8. 3. 21:12"}), "21:12")
        self.assertEqual(observed_time({"used_time": ""}), "")
        self.assertEqual(observed_time({"used_time": "unknown"}), "")

    def test_potential_aliases_never_merge_financial_records(self):
        rows = [
            {"merchant": "주식회사 송이향", "amount": 10000},
            {"merchant": "송이향", "amount": 25000},
            {"merchant": "월수금통돼지김치찌개(의왕오전점)", "amount": 20000},
            {"merchant": "월수금통돼지김치찌개", "amount": 30000}
        ]
        original = copy.deepcopy(rows)
        suggestions = suspected_alias_groups(rows)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(sorted(suggestions[0]["source_names"]), ["송이향", "주식회사 송이향"])
        self.assertEqual(rows, original)

    def test_misclassified_cafe_and_unconfirmed_role_not_ranked(self):
        rows = [
            {"row_id": str(i), "merchant": "컴포즈커피" if i % 2 else "구이마을",
             "source_period": [2026, 9, None], "used_date": "2026-09-12",
             "role": "의장" if i % 3 else "", "amount": 75000, "purpose": "간담회"}
            for i in range(193)
        ]
        original = copy.deepcopy(rows)
        result, decisions, preview, aliases = assess_venues(rows)
        self.assertEqual(result["source_validation"], "PASS")
        self.assertEqual(result["identity_verified_merchants"], 0)
        self.assertFalse(result["publish"])
        self.assertEqual({x["merchant"] for x in preview}, {"구이마을"})
        self.assertTrue(all(x["publication_status"] == "HOLD_ENTITY_REVIEW" for x in preview))
        self.assertEqual(rows, original)

    def test_out_of_period_data_fails_closed(self):
        rows = [
            {"row_id": str(i), "merchant": "구이마을",
             "source_period": [2026, 10, None], "used_date": "2026-09-12",
             "role": "의장", "amount": 55000, "purpose": "간담회"}
            for i in range(193)
        ]
        result, *_ = assess_venues(rows)
        self.assertEqual(result["source_validation"], "HOLD")
        self.assertIn("candidate_official_period_mismatch", result["failures"])


if __name__ == "__main__":
    unittest.main()
