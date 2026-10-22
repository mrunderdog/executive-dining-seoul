import json
import unittest
from pathlib import Path
from published_sources import SOURCE_SPECS, _build_source_records, ROOT

class IcheonVenueReviewTests(unittest.TestCase):
    def test_complete_candidate_snapshot_and_no_unearned_payment_verification(self):
        src=json.loads((ROOT/"sources/icheon_venue_review.json").read_text(encoding="utf-8"))
        candidates=json.loads((ROOT/"reports/icheon-executive-candidates.json").read_text(encoding="utf-8"))["candidates"]
        self.assertEqual(src["source"],"icheon")
        self.assertEqual([r["merchant"] for r in src["candidates"]],[r["merchant"] for r in candidates])
        self.assertTrue(all(not r["payment_branch_verified"] for r in src["candidates"]))
        self.assertEqual(len(src["candidates"]),77)
        self.assertEqual(len(set(r["merchant"] for r in src["candidates"])),77)

    def test_no_unverified_branch_is_asserted_as_verified_or_autolocated(self):
        records=_build_source_records("icheon",SOURCE_SPECS["icheon"])
        self.assertTrue(records)
        self.assertTrue(all(not r["payment_branch_verified"] for r in records))
        self.assertTrue(all(r["payment_branch_review_status"] for r in records))
        self.assertFalse(any(r["name"]=="동아기획" for r in records))

if __name__=="__main__": unittest.main()
