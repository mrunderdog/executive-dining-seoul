"""Official Police spending place, attendance and identity safeguards."""
import copy
import unittest
from police_expense_publication import load_police_expense_records, select_expense_venues, STAGING, MANIFEST
from global_entities import merge_global_entities
import json

class PoliceExpenseSitePolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads(STAGING.read_text(encoding="utf-8"))
        cls.manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    def test_live_official_rows_and_amount(self):
        records=load_police_expense_records()
        self.assertEqual(len(records),1)
        x=records[0]
        self.assertEqual(x["name"],"사조미가")
        self.assertEqual(x["evidence"]["spending_events"],2)
        self.assertEqual(x["evidence"]["spend"],318000)
        self.assertEqual(x["evidence"]["visits"],0)
        self.assertEqual(x["executive"]["top_official_visits"],0)
        self.assertEqual(x["attendance_status"],"NOT_ESTABLISHED")
        self.assertTrue(x["source_verified_expense_only"])
        self.assertEqual(x["evidence"]["roles"][0]["visits"],0)
        self.assertTrue(all(z["attendance_status"]=="NOT_ESTABLISHED" for z in x["evidence"]["recent"]))
        self.assertTrue(all(z["expense_user_only"] for z in x["evidence"]["recent"]))
    def test_published_site_global_entity_keeps_spending_not_visits(self):
        x=load_police_expense_records()[0]
        merged=merge_global_entities({"records":[x]})["records"][0]
        self.assertEqual(merged["evidence"]["spending_events"],2)
        self.assertEqual(merged["evidence"]["visits"],0)
        self.assertEqual(merged["evidence"]["spend"],318000)
    def test_unrelated_merchants_and_companies_never_published(self):
        copy_doc=copy.deepcopy(self.doc)
        for row in copy_doc["transactions"]:
            row["merchant"]="스타벅스코리아"
        self.assertEqual(select_expense_venues(copy_doc,self.manifest),[])
    def test_fake_attendance_claim_is_not_accepted(self):
        copy_doc=copy.deepcopy(self.doc)
        for row in copy_doc["transactions"]:
            row["attendance_evidence"]="CONFIRMED"
        self.assertEqual(select_expense_venues(copy_doc,self.manifest),[])
    def test_pdf_hash_and_role_cannot_drift(self):
        for field,value in (("pdf_sha256","0"*64),("role","경찰청차장"),
                            ("source_url","https://www.police.go.kr.bad.test/a.pdf"),
                            ("source_detail_url","https://www.police.go.kr.bad.test/detail")):
            bad=copy.deepcopy(self.doc)
            for row in bad["transactions"]:
                row[field]=value
            self.assertEqual(select_expense_venues(bad,self.manifest),[],field)
    def test_address_and_evidence_must_be_explicit(self):
        for field,value in (("address",""),("address_evidence_urls",["https://example.test/single"]),
                            ("attendance_confirmed",True)):
            m=copy.deepcopy(self.manifest)
            m["venues"][0][field]=value
            with self.assertRaises(ValueError,msg=field):
                select_expense_venues(self.doc,m)
    def test_no_plain_visit_inference(self):
        x=load_police_expense_records()[0]
        self.assertNotIn("방문 확인",x["why"])
        self.assertIn("실제 식사 참석 여부는 확인되지 않았",x["why"])

if __name__=="__main__":unittest.main()
