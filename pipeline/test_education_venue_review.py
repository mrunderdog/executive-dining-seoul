"""Offline tests of conservative official dining review gate."""
import unittest
from review_education_venues import review
from education_police_source_probe import police_same_host_fallback, police_official_variants
from venue_eligibility import is_non_venue_merchant

class VenueReviewTests(unittest.TestCase):
    def setUp(self):
        self.src=[{"key":"gyeonggi_education","institution":"경기도교육청","official_hosts":["goe.go.kr"]}]
        self.row={"source_key":"gyeonggi_education","row_id":"test1","role":"제2부교육감",
             "role_source":"posting_title","target":"제2부교육감 및 관계자 3명",
             "merchant":"밀가마국시집","used_date":"2025-04-02","amount":60000,
             "source_url":"https://www.goe.go.kr/real.pdf",
             "source_detail_url":"https://www.goe.go.kr/detail"}
    def test_retail_and_florist_labels_not_restaurants(self):
        for label in ("이마트몰","화월청과","우성화원"):
            self.assertTrue(is_non_venue_merchant(label),label)
            row={**self.row,"merchant":label}
            result=review([row],self.src)
            self.assertEqual(result["reviewable_transactions"],0)
            self.assertEqual(result["excluded"]["GENERIC_BILLER_OR_NON_VENUE"],1)
        self.assertFalse(is_non_venue_merchant("수원갈비상회"))
    def test_official_police_hostname_attempts(self):
        original="https://www.police.go.kr/user/bbs/BD_selectBbs.do?q_bbsCode=1025"
        urls=police_official_variants(original)
        self.assertEqual(len(urls),4)
        self.assertEqual(urls[0],original)
        self.assertTrue(any(u.startswith("https://police.go.kr/user/bbs/") for u in urls))
        self.assertTrue(any(u.startswith("https://www.police.go.kr/BZRKZR/user/bbs/") for u in urls))
        self.assertTrue(all("q_bbsCode=1025" in u for u in urls))
        self.assertEqual(police_official_variants("https://not-police.go.kr/user/bbs/x"),["https://not-police.go.kr/user/bbs/x"])
        self.assertEqual(police_official_variants("http://police.go.kr/user/bbs/x"),["http://police.go.kr/user/bbs/x"])
    def test_police_fallback_is_same_host_only(self):
        a="https://www.police.go.kr/user/bbs/BD_selectBbs.do?q_bbsCode=1025"
        self.assertEqual(police_same_host_fallback(a),
          "https://www.police.go.kr/BZRKZR/user/bbs/BD_selectBbs.do?q_bbsCode=1025")
        self.assertEqual(police_same_host_fallback("https://evil.example/user/bbs/x"),"")
        self.assertEqual(police_same_host_fallback("http://www.police.go.kr/user/bbs/x"),"")
    def test_unverified_venue_is_not_auto_published(self):
        out=review([self.row],self.src)
        self.assertEqual(out["reviewable_transactions"],1)
        self.assertEqual(out["candidates"][0]["venue_identity_status"],"MANUAL_VERIFICATION_REQUIRED")
        self.assertFalse(out["publication_enabled"])
    def test_office_staff_not_official(self):
        out=review([{**self.row,"target":"제2부교육감실 직원 3명"}],self.src)
        self.assertEqual(out["reviewable_transactions"],0)
        self.assertEqual(out["excluded"]["OFFICIAL_PRESENCE_UNCONFIRMED"],1)
    def test_duplicate_row_id_not_double_counted(self):
        out=review([self.row,self.row],self.src)
        self.assertEqual(out["reviewable_transactions"],1)
    def test_generic_biller_and_untrusted_url_excluded(self):
        a=review([{**self.row,"merchant":"쿠팡"}],self.src)
        b=review([{**self.row,"source_url":"https://goe.go.kr.evil.test/p.pdf"}],self.src)
        self.assertEqual(a["reviewable_transactions"],0)
        self.assertEqual(b["reviewable_transactions"],0)
if __name__=="__main__":unittest.main()
