import json
import unittest
from pathlib import Path

from source_address_evidence import curated_location, REGISTRY
from extra_published import central_records, public_enterprise_records
from published_sources import _build_source_records, SOURCE_SPECS

class CuratedAddressEvidenceTest(unittest.TestCase):
    def test_only_explicitly_approved_same_cohort_venue_resolves(self):
        ob=curated_location("central_executive","오발탄 세종점")
        ch=curated_location("public_enterprise_leadership","창고43샛강점")
        self.assertIn("도움1로 7",ob["address"])
        self.assertIn("여의대방로 376",ch["address"])
        self.assertFalse(ob["payment_branch_verified"])
        self.assertFalse(ch["individual_attendance_verified"])
        self.assertIsNone(curated_location("central_executive","일품진진수라 광화문점"))
        self.assertIsNone(curated_location("public_enterprise_leadership","오발탄 세종점"))
        self.assertIn("세종대로 14",curated_location("central_executive","모담 서울역점")["address"])
        self.assertIn("국회대로76길 16",curated_location("central_executive","가시리 여의도점")["address"])
        self.assertIn("여의대방로67길 21",curated_location("public_enterprise_leadership","우들목여의도점")["address"])
        self.assertIsNone(curated_location("public_enterprise_leadership","영덕집"))
        so=curated_location("central_executive","소쿠리밥상세종청사점")
        jin=curated_location("central_executive","진가와코리아 광화문점")
        self.assertIn("한누리대로 411",so["address"])
        self.assertIn("종로1길 50",jin["address"])
        self.assertFalse(so["payment_branch_verified"])
        self.assertFalse(jin["individual_attendance_verified"])


    def test_three_new_exact_venue_locations_without_payment_identity(self):
        for source, name, road in [
            ("gwangmyeong", "폴바셋 광명철산DT점", "오리로 883"),
            ("suwon", "소미담 수원시청점", "경수대로428번길 15"),
            ("suwon", "소소한우", "센트럴타운로 94"),
        ]:
            evidence=curated_location(source,name)
            self.assertIsNotNone(evidence)
            self.assertIn(road,evidence["address"])
            self.assertFalse(evidence["payment_branch_verified"])
            rows={r["name"]:r for r in _build_source_records(source,SOURCE_SPECS[source])}
            self.assertIn(name,rows)
            self.assertIn(road,rows[name]["address"])
            self.assertFalse(rows[name]["payment_branch_verified"])
        self.assertIsNone(curated_location("central_executive","차이(chai)797 광화문점"))
        self.assertIsNone(curated_location("central_executive","세종 오이시"))

    def test_five_new_verified_venue_addresses_are_not_payment_proof(self):
        for source, name, road in [
            ("bupyeong","진명숯불구이","함봉로36번길 8-15"),
            ("anseong","백제찌개촌","아양1로 77-31"),
            ("anseong","더푸짐한밥상","낙원길 112"),
            ("osan","백가네부대찌게","운천로 89"),
            ("ganghwa","양푼생돼지김치찌개 강화점","강화대로409번길 4"),
        ]:
            loc=curated_location(source,name)
            self.assertIsNotNone(loc,(source,name))
            self.assertIn(road,loc["address"])
            self.assertFalse(loc["payment_branch_verified"])
            records={r["name"]:r for r in _build_source_records(source,SOURCE_SPECS[source])}
            self.assertIn(name,records)
            self.assertIn(road,records[name]["address"])
            self.assertFalse(records[name]["payment_branch_verified"])

    def test_third_batch_exact_location_with_no_payment_identity(self):
        for source,name,road in [
            ("gwacheon","문원한우마을","별양상가1로 10"),
            ("central_executive","저림숙성그릴","보듬3로 8-27"),
            ("central_executive","이태형의 메구미","도움8로 91"),
        ]:
            match=curated_location(source,name)
            self.assertIsNotNone(match,(source,name))
            self.assertIn(road,match["address"])
            self.assertFalse(match["payment_branch_verified"])
            if source=="central_executive":
                records={x["name"]:x for x in central_records()}
            else:
                records={x["name"]:x for x in _build_source_records(source,SOURCE_SPECS[source])}
            self.assertIn(name,records)
            self.assertIn(road,records[name]["address"])
            self.assertFalse(records[name]["payment_branch_verified"])
        for cohort,name in (("central_executive","만복림"),("public_enterprise_leadership","초원복국"),("central_executive","해초섬")):
            self.assertIsNone(curated_location(cohort,name))

    def test_six_correlated_restaurants_not_six_card_branch_claims(self):
        expected=[
            ("봉피양(경복궁)","자하문로 20"),
            ("로씨니","북촌로 18"),
            ("경성한우국밥","새문안로5가길 32"),
            ("도담도담 민물장어","한누리대로 583"),
            ("브이아이피참치(주)","세종대로 135"),
            ("시청해우리","서소문로 95"),
        ]
        records={x["name"]:x for x in central_records()}
        for name,road in expected:
            match=curated_location("central_executive",name)
            self.assertIsNotNone(match,name)
            self.assertIn(road,match["address"])
            self.assertFalse(match["payment_branch_verified"])
            self.assertFalse(match["individual_attendance_verified"])
            self.assertIn(name,records)
            self.assertIn(road,records[name]["address"])
            self.assertFalse(records[name]["payment_branch_verified"])
        self.assertIsNone(curated_location("central_executive","대선칼국수"))
        self.assertIsNone(curated_location("ongjin","청풍면옥"))

    def test_fail_closed_for_unsubstantiated_approval(self):
        registry={"entries":[{"cohort":"central_executive","merchant":"테스트점",
            "status":"APPROVED_VENUE_LOCATION","address":"서울 중구 임의로 1",
            "basis":"EXACT_NAMED_BRANCH_CORROBORATED",
            "evidence":[{"url":"https://one.example/location"}]}]}
        self.assertIsNone(curated_location("central_executive","테스트점",registry))
        registry["entries"][0]["evidence"].append({"url":"http://two.example/location"})
        self.assertIsNone(curated_location("central_executive","테스트점",registry))

    def test_source_candidate_files_unchanged_and_only_new_branches_enriched(self):
        root=Path(__file__).resolve().parents[1]
        central=json.loads((root/"reports/central-executive-candidates.json").read_text(encoding="utf-8"))["candidates"]
        public=json.loads((root/"reports/public-enterprise-candidates.json").read_text(encoding="utf-8"))["candidates"]
        self.assertFalse(next(x for x in central if x["merchant"]=="오발탄 세종점")["address"])
        self.assertFalse(next(x for x in public if x["merchant"]=="창고43샛강점")["address"])
        central_rows={x["name"]:x for x in central_records()}
        public_rows={x["name"]:x for x in public_enterprise_records()}
        for rec in (central_rows["오발탄 세종점"],public_rows["창고43샛강점"]):
            self.assertTrue(rec["address"])
            self.assertEqual(rec["venue_location_match_basis"],"EXACT_NAMED_BRANCH_OFFICIAL_BRAND")
            self.assertGreaterEqual(len(rec["venue_location_evidence_urls"]),2)
            self.assertFalse(rec["payment_branch_verified"])
            self.assertFalse(rec["personal_attendance_verified"])
            self.assertIn("미확인",rec["business"]["status"])
        # Already enriched in September: no duplicate new-approval claim.
        self.assertIn("종로5길 7",central_rows["일품진진수라 광화문점"]["address"])
        self.assertIsNone(central_rows["일품진진수라 광화문점"]["venue_location_match_basis"])
        self.assertIn("세종대로 14",central_rows["모담 서울역점"]["address"])
        for name in ("소쿠리밥상세종청사점", "진가와코리아 광화문점"):
            rec=central_rows[name]
            self.assertEqual(rec["venue_location_match_basis"],"EXACT_NAMED_BRANCH_CORROBORATED")
            self.assertFalse(rec["payment_branch_verified"])
            self.assertFalse(rec["personal_attendance_verified"])
            self.assertGreaterEqual(len(rec["venue_location_evidence_urls"]), 2)

        self.assertIn("여의대방로67길 21",public_rows["우들목여의도점"]["address"])

