"""Source discovery trace regressions: preserve evidence but never publish partial discovery."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from capital_backfill import DiscoveryTrace, SOURCES, discover_source


class IncheonTraceTests(unittest.TestCase):
    def test_detail_failure_preserves_listing_and_failed_post(self):
        src = next(s for s in SOURCES if s.key == "incheon_council")
        listing_url = src.listing_template.format(page=1)
        detail_url = "https://www.icouncil.go.kr/main/bbs/bbsMsgDetail.do?msg_seq=1320&bcd=infordisc"
        listing = f'<a href="{detail_url}">2026년 8월 환경교통위원장 업무추진비 집행내역</a>'
        def fake_fetch(url):
            if url == listing_url:
                return listing
            raise TimeoutError("official detail unavailable")
        with tempfile.TemporaryDirectory() as directory:
            trace = DiscoveryTrace(Path(directory) / "trace.json", "incheon_council", (2026,7), (2026,10))
            with patch("capital_backfill.fetch_text", side_effect=fake_fetch):
                posts = discover_source(src, (2026,7), (2026,10), trace=trace)
            evidence = json.loads(trace.path.read_text(encoding="utf-8"))
            self.assertFalse(evidence["publication_authorized"])
            self.assertEqual(evidence["source"], "incheon_council")
            self.assertTrue(any(x["stage"] == "listing_fetched" and x["page"] == 1 for x in evidence["events"]))
            self.assertTrue(any(x["stage"] == "detail_observed" and "TimeoutError" in str(x.get("error")) for x in evidence["events"]))
            self.assertTrue(any(x.get("error") for x in posts))

    def test_trace_survives_interrupted_discovery_without_success_label(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "trace.json"
            trace = DiscoveryTrace(target, "incheon_council", (2026,7), (2026,10))
            trace.add("listing_fetched", page=1, url="official", html_sha256="a"*64, anchor_count=5)
            persisted = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(persisted["status"], "INCOMPLETE")
            self.assertFalse(persisted["publication_authorized"])
            self.assertEqual(persisted["events"][-1]["page"], 1)

if __name__ == "__main__":
    unittest.main()
