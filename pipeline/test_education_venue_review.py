"""Offline tests of conservative official dining review gate."""
import unittest
from review_education_venues import review

class VenueReviewTests(unittest.TestCase):
    def setUp(self):
        self.src=[{"key":"gyeonggi_education","institution":"경기도교육청","official_hosts":["goe.go.kr"]}]
        self.row={"source_key":"gyeonggi_education","row_id":"test1","role":"제2부교육감",
             "role_source":"posting_title","target":"제2부교육감 및 관계자 3명",
             "merchant":"밀가마국시집","used_date":"2025-04-02","amount":60000,
             "source_url":"https://www.goe.go.kr/real.pdf",
             "source_detail_url":"https://www.goe.go.kr/detail"}
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
