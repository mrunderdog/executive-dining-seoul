import json
import unittest
from published_sources import ROOT, SOURCE_SPECS, _build_source_records

class MulticouncilReviewTests(unittest.TestCase):
    def test_candidate_coverage(self):
        for key, count in (("icheon", 77), ("ansan", 56), ("hwaseong", 89)):
            doc=json.loads((ROOT/"sources"/f"{key}_venue_review.json").read_text(encoding="utf-8"))
            original=json.loads((ROOT/"reports"/f"{key}-executive-candidates.json").read_text(encoding="utf-8"))
            self.assertEqual(len(doc["candidates"]),count)
            self.assertEqual([r["merchant"] for r in doc["candidates"]],[r["merchant"] for r in original["candidates"]])
            self.assertTrue(all(not r["payment_branch_verified"] for r in doc["candidates"]))
            self.assertTrue(all(not r["publish_as_verified_payment_location"] for r in doc["candidates"]))
    def test_similar_merchant_names_not_merged_and_no_false_payment_branch(self):
        review=json.loads((ROOT/"sources/hwaseong_venue_review.json").read_text(encoding="utf-8"))
        names={r["merchant"]:r for r in review["candidates"]}
        for name in ("훈장골","훈장골갈비집"):
            self.assertEqual(names[name]["review_status"],"POSSIBLE_ALIAS_NOT_PROVEN")
        for source in ("icheon","ansan","hwaseong"):
            records=_build_source_records(source,SOURCE_SPECS[source])
            self.assertTrue(all(not r["payment_branch_verified"] for r in records))
if __name__ == "__main__": unittest.main()
