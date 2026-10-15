import json
import unittest
from pathlib import Path

from source_address_evidence import curated_location, REGISTRY
from extra_published import central_records, public_enterprise_records

class CuratedAddressEvidenceTest(unittest.TestCase):
    def test_only_explicitly_approved_same_cohort_venue_resolves(self):
        ob=curated_location("central_executive","오발탄 세종점")
        jj=curated_location("central_executive","일품진진수라 광화문점")
        self.assertIn("도움1로 7",ob["address"])
        self.assertIn("종로5길 7",jj["address"])
        self.assertFalse(ob["payment_branch_verified"])
        self.assertFalse(jj["individual_attendance_verified"])
        self.assertIsNone(curated_location("public_enterprise_leadership","오발탄 세종점"))
        self.assertIsNone(curated_location("central_executive","모담 서울역점"))
        self.assertIsNone(curated_location("central_executive","가시리 여의도점"))
        self.assertIsNone(curated_location("public_enterprise_leadership","우들목여의도점"))
        self.assertIsNone(curated_location("public_enterprise_leadership","영덕집"))

    def test_fail_closed_for_unsubstantiated_approval(self):
        registry={"entries":[{"cohort":"central_executive","merchant":"테스트점",
            "status":"APPROVED_VENUE_LOCATION","address":"서울 중구 임의로 1",
            "basis":"EXACT_NAMED_BRANCH_CORROBORATED",
            "evidence":[{"url":"https://one.example/location"}]}]}
        self.assertIsNone(curated_location("central_executive","테스트점",registry))
        registry["entries"][0]["evidence"].append({"url":"http://two.example/location"})
        self.assertIsNone(curated_location("central_executive","테스트점",registry))

    def test_published_central_only_enriches_approved_locations(self):
        candidates=json.loads((Path(__file__).resolve().parents[1]/"reports/central-executive-candidates.json").read_text(encoding="utf-8"))["candidates"]
        self.assertFalse(next(x for x in candidates if x["merchant"]=="오발탄 세종점")["address"])
        self.assertFalse(next(x for x in candidates if x["merchant"]=="일품진진수라 광화문점")["address"])
        rows={x["name"]:x for x in central_records()}
        for merchant in ("오발탄 세종점","일품진진수라 광화문점"):
            rec=rows[merchant]
            self.assertTrue(rec["address"])
            self.assertTrue(rec["venue_location_match_basis"])
            self.assertEqual(len(rec["venue_location_evidence_urls"]),2)
            self.assertFalse(rec["payment_branch_verified"])
            self.assertFalse(rec["personal_attendance_verified"])
            self.assertIn("미확인",rec["business"]["status"])
        self.assertEqual(rows["모담 서울역점"]["address"],"")
        enterprises={x["name"]:x for x in public_enterprise_records()}
        self.assertEqual(enterprises["우들목여의도점"]["address"],"")

if __name__=="__main__":
    unittest.main()
