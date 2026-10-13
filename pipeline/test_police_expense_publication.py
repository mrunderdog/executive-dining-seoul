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
        self.assertEqual(len(records),8)
        x=next(r for r in records if r["name"]=="사조미가")
        self.assertEqual(x["name"],"사조미가")
        self.assertEqual(x["evidence"]["spending_events"],5)
        self.assertEqual(x["evidence"]["spend"],900000)
        self.assertEqual(x["evidence"]["visits"],0)
        self.assertEqual(x["executive"]["top_official_visits"],0)
        self.assertEqual(x["attendance_status"],"NOT_ESTABLISHED")
        self.assertTrue(x["source_verified_expense_only"])
        self.assertEqual(x["evidence"]["roles"][0]["visits"],0)
        self.assertTrue(all(z["attendance_status"]=="NOT_ESTABLISHED" for z in x["evidence"]["recent"]))
        self.assertTrue(all(z["expense_user_only"] for z in x["evidence"]["recent"]))
    def test_published_site_global_entity_keeps_spending_not_visits(self):
        x=next(r for r in load_police_expense_records() if r["name"]=="사조미가")
        merged=merge_global_entities({"records":[x]})["records"][0]
        self.assertEqual(merged["evidence"]["spending_events"],5)
        self.assertEqual(merged["evidence"]["visits"],0)
        self.assertEqual(merged["evidence"]["spend"],900000)
    def test_sajo_multi_pdf_expenses_are_exactly_allowed(self):
        x=next(r for r in load_police_expense_records() if r["name"]=="사조미가")
        roles={z["role"]:z for z in x["evidence"]["roles"]}
        self.assertEqual(x["executive"]["roles"],3)
        self.assertEqual(x["executive"]["top_official_visits"],0)
        self.assertEqual(len(x["evidence"]["source_rows"]),5)
        self.assertEqual(roles["경무인사기획관 (집행 명의)"]["spending_events"],2)
        self.assertEqual(roles["치안정보국장 (집행 명의)"]["spending_events"],1)
        self.assertEqual(roles["범죄예방대응국장 (집행 명의)"]["spending_events"],2)
        m=copy.deepcopy(self.manifest)
        source=next(v for v in m["venues"] if v["merchant"]=="사조미가")["additional_sources"][0]
        source["approved_row_ids"]=["fabricated-id"]
        y=next(r for r in select_expense_venues(self.doc,m) if r["name"]=="사조미가")
        self.assertEqual(y["evidence"]["spending_events"],4)
        source["approved_row_ids"]=[]
        with self.assertRaises(ValueError):
            select_expense_venues(self.doc,m)

    def test_new_scanned_venues_pinned_and_not_attendance(self):
        by={r["name"]:r for r in load_police_expense_records()}
        for name,amount in {"설마중":347000,"차이(Chai)797 시청":300000,
                            "산청숯불가든 을지로":307000,"(주)어반가든":208300}.items():
            self.assertEqual(by[name]["evidence"]["spend"],amount)
            self.assertEqual(by[name]["evidence"]["visits"],0)
            self.assertEqual(by[name]["evidence"]["spending_events"],1)
        m=copy.deepcopy(self.manifest)
        target=next(v for v in m["venues"] if v["merchant"]=="설마중")
        target.pop("approved_row_ids")
        self.assertNotIn("설마중",[v["name"] for v in select_expense_venues(self.doc,m)])
        target["approved_row_ids"]=["fabricated-id"]
        self.assertNotIn("설마중",[v["name"] for v in select_expense_venues(self.doc,m)])

    def test_probable_location_match_is_not_claimed_as_fact(self):
        by={x["name"]:x for x in load_police_expense_records()}
        for name,count,amount in [("남원추어탕",4,406000),("미소",2,242000),("퍼스트플로어",2,233400)]:
            row=by[name]
            self.assertEqual(row["evidence"]["spending_events"],count)
            self.assertEqual(row["evidence"]["spend"],amount)
            self.assertEqual(row["evidence"]["visits"],0)
            self.assertEqual(row["business"]["verification_confidence"],"PROBABLE")
            self.assertIn("확정되지 않았",row["why"])

    def test_uncertain_police_location_survives_cross_institution_merge(self):
        probable=next(r for r in load_police_expense_records() if r["name"]=="남원추어탕")
        self.assertEqual(probable["location_match_confidence"],"PROBABLE_NAME_AND_PROXIMITY")
        other=copy.deepcopy(probable)
        other["origin"]="서울시청"
        other["institution"]="서울시청"
        other["institutions"]=["서울시청"]
        other["published_source"]="seoul_executive"
        other["source_verified_expense_only"]=False
        other["location_match_confidence"]="ADDRESS_CORROBORATED"
        other["evidence"]["spending_events"]=0
        other["evidence"]["visits"]=1
        other["evidence"]["spend"]=0
        other["evidence"]["source_rows"]=[]
        other["evidence"]["recent"]=[]
        merged=merge_global_entities({"records":[probable,other]})["records"]
        self.assertEqual(len(merged),1)
        venue=merged[0]
        self.assertEqual(venue["police_expense_venue_match_status"],"PROBABLE_NAME_AND_PROXIMITY")
        self.assertEqual(venue["police_expense_uncertain_spending_events"],4)
        self.assertIn("경찰청 관련 교차기관 신호",venue["why"])
        self.assertEqual(venue["evidence"]["spending_events"],4)

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
        for field,value in (("pdf_sha256","0"*64),("role","없는직책-변조"),
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
        x=next(r for r in load_police_expense_records() if r["name"]=="사조미가")
        self.assertNotIn("방문 확인",x["why"])
        self.assertIn("실제 식사 참석 여부는 확인되지 않았",x["why"])

if __name__=="__main__":unittest.main()
