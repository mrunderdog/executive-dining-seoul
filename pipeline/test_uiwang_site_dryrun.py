"""Protect independent municipalities during Uiwang score-only staging."""
import unittest
from audit_uiwang_site_dryrun import ranking_input_allowed


class ScopedRankingTests(unittest.TestCase):
    def test_unrelated_sources_remain_visible(self):
        for source in ("goyang", "bucheon", "guri", "icheon", "hwaseong", "incheon_council"):
            observed = {"row_id": "other-1", "source_key": source}
            self.assertTrue(ranking_input_allowed(observed, {"ok"}, {"historic"}, lambda r: True))
    def test_uiwang_only_eligible_new_rows(self):
        base = {"historic"}
        allowed = {"ok"}
        self.assertFalse(ranking_input_allowed({"row_id": "unreviewed", "source_key": "uiwang"}, allowed, base, lambda r: True))
        self.assertTrue(ranking_input_allowed({"row_id": "ok", "source_key": "uiwang"}, allowed, base, lambda r: True))
        self.assertTrue(ranking_input_allowed({"row_id": "historic", "source_key": "uiwang"}, allowed, base, lambda r: True))
    def test_original_source_rule_is_still_required(self):
        self.assertFalse(ranking_input_allowed({"row_id": "other", "source_key": "guri"}, set(), set(), lambda r: False))


if __name__ == "__main__":
    unittest.main()
