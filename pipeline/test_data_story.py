#!/usr/bin/env python3
"""Regression tests for public infographic semantics."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_story import build_data_story


class DataStoryTest(unittest.TestCase):
    def test_overlap_and_quality_scope(self):
        records = [
            {"origins": ["중앙정부", "공기업·공공기관"], "address": "서울 종로구 A로 1",
             "lat": 37.5, "lon": 127.0, "cross_institution": {"is_cross": True},
             "executive": {"top_official_visits": 2}, "evidence": {"date_max": "2025-01-01"}},
            {"origin": "경찰청", "address": "", "cross_institution": {"is_cross": False},
             "evidence": {"date_max": "bad-date"}},
        ]
        quality = {"passed": True, "warnings": ["example"], "checks": {"source_health": {
            "a": {"diagnosis": "PUBLISHED"},
            "b": {"diagnosis": "INGESTION_REVIEW"},
            "c": {"diagnosis": "BELOW_PUBLICATION_THRESHOLDS"},
        }}}
        result = build_data_story(records, quality, "2026-10-16T00:00:00+00:00")
        self.assertEqual(result["published"], {
            "venues": 2, "with_address": 1, "mapped": 1,
            "cross_institution": 1, "top_official": 1,
        })
        self.assertEqual(sum(x["published_venues"] for x in result["source_groups"]), 3)
        self.assertEqual(result["latest_disclosed_record_date"], "2025-01-01")
        self.assertEqual(result["health"]["attention_sources"], 1)
        self.assertEqual(result["health"]["diagnosed_sources"], 3)
        self.assertIsNone(result["health"]["confirmed_refresh_failures"])

    def test_missing_report_must_not_be_reported_success(self):
        result = build_data_story([{"origin": "중앙정부"}], None, "2026-10-16T00:00:00Z")
        self.assertIsNone(result["health"]["qa_passed"])
        self.assertIsNone(result["health"]["qa_warning_count"])
        self.assertIsNone(result["health"]["attention_sources"])
        self.assertEqual(result["published"]["mapped"], 0)

if __name__ == "__main__":
    unittest.main()
