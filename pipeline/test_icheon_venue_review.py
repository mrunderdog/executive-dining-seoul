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
        self.assertEqual(len(src["candidates"]),90)
        self.assertEqual(sum(r["review_status"] == "NOT_REVIEWED" for r in src["candidates"]),82)
        self.assertEqual(sum(r["review_status"] != "NOT_REVIEWED" for r in src["candidates"]),8)
        self.assertEqual(src["summary"]["verified_payment_branches"],0)
        self.assertEqual(len(set(r["merchant"] for r in src["candidates"])),90)

    def test_new_june_candidates_have_transaction_lineage_without_branch_claim(self):
        src=json.loads((ROOT/"sources/icheon_venue_review.json").read_text(encoding="utf-8"))
        raw=json.loads((ROOT/"data/raw/icheon_expense.json").read_text(encoding="utf-8"))
        rows={r["row_id"]:r for r in raw["rows"]}
        new=[x for x in src["candidates"] if x.get("candidate_source_row_ids")]
        self.assertEqual(len(new),13)
        for candidate in new:
            self.assertEqual(candidate["review_status"],"NOT_REVIEWED")
            self.assertFalse(candidate["payment_branch_verified"])
            self.assertFalse(candidate["publish_as_verified_payment_location"])
            matched=[rows[row_id] for row_id in candidate["candidate_source_row_ids"]]
            leadership=[r for r in matched if r.get("role") in ("의장","부의장")]
            self.assertEqual(len(matched),len(leadership))
            self.assertEqual(len(matched),candidate["source_visits"])
            self.assertEqual(sum(r["amount"] for r in matched),candidate["source_spend"])
            self.assertEqual({r["merchant"] for r in matched},{candidate["merchant"]})
            self.assertTrue(all(r["used_date"].startswith("2026-06") for r in matched))
            self.assertEqual({r["source_attachment_url"] for r in matched},set(candidate["candidate_source_attachment_urls"]))

    def test_no_unverified_branch_is_asserted_as_verified_or_autolocated(self):
        records=_build_source_records("icheon",SOURCE_SPECS["icheon"])
        self.assertTrue(records)
        self.assertTrue(all(not r["payment_branch_verified"] for r in records))
        self.assertTrue(all(r["payment_branch_review_status"] for r in records))
        self.assertFalse(any(r["name"]=="동아기획" for r in records))

if __name__=="__main__": unittest.main()
