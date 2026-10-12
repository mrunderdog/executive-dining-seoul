import json
import unittest
from review_police_expense_merchants import review, STAGED, VENUES

class PoliceMerchantReview(unittest.TestCase):
    def setUp(self):
        self.staged=json.loads(STAGED.read_text(encoding="utf-8"))
        self.manifest=json.loads(VENUES.read_text(encoding="utf-8"))
    def test_current_source_totals(self):
        d=review(self.staged,self.manifest)
        self.assertFalse(d["publication_enabled"])
        self.assertGreaterEqual(d["staged_transaction_count"],20)
        self.assertEqual(d["staged_transaction_count"],len(self.staged["transactions"]))
        self.assertEqual(sum(x["transactions"] for x in d["merchants"]),len(self.staged["transactions"]))
        self.assertEqual(sum(x["amount_won"] for x in d["merchants"]),sum(x["amount"] for x in self.staged["transactions"]))
        self.assertGreaterEqual(sum(x["amount_won"] for x in d["merchants"]),3691800)
        by={x["merchant"]:x for x in d["merchants"]}
        self.assertEqual(by["사조미가"]["status"],"VENUE_IDENTITY_APPROVED")
        self.assertGreaterEqual(by["사조미가"]["transactions"],2)
        self.assertEqual(by["사조미가"]["approved_transactions"],5)
        self.assertEqual(by["사조미가"]["remaining_review_transactions"],by["사조미가"]["transactions"]-5)
        self.assertEqual(by["남원추어탕"]["status"],"VENUE_LOCATION_NOT_VERIFIED")
        self.assertEqual(by["스타벅스코리아"]["status"],"NON_DINING_OR_GENERIC_BILLER")
        self.assertFalse(any(x["attendance_confirmed"] for x in d["merchants"]))
    def test_review_queue_preserves_row_level_provenance(self):
        d=review(self.staged,self.manifest)
        for merchant in d["merchants"]:
            self.assertEqual(len(merchant["pending_row_ids"]),merchant["remaining_review_transactions"])
            self.assertFalse(merchant["attendance_confirmed"])
            if merchant["status"]=="NON_DINING_OR_GENERIC_BILLER":
                self.assertEqual(merchant["review_priority"],"EXCLUDE_OR_RECONCILE")
            if merchant["remaining_review_transactions"]==0:
                self.assertEqual(merchant["review_priority"],"NOT_REQUIRED")

    def test_scanned_pdf_visual_review_is_source_reconciled_and_unpublished(self):
        reviewed=[x for x in self.staged["transactions"] if x.get("transcription_method")=="HUMAN_VISUAL_REVIEW_OF_OFFICIAL_PDF"]
        self.assertEqual(len(reviewed),17)
        self.assertEqual(sum(x["amount"] for x in reviewed),3041260)
        expected={
            "1139d2be05e073fe6f44c9a7666b23bae26e306d21fbcd7daaa9d6e13f07b08b":(5,883000),
            "c22920bba55108f288f36c2636e0d98faface0fd1c18c2ded9ec8c184256279a":(8,1449960),
            "172baf2349b9315e866ca530623cfe23106d34fc5a1273cb61f3a550dc66f134":(4,708300),
        }
        for sha,(count,total) in expected.items():
            rows=[x for x in reviewed if x["pdf_sha256"]==sha]
            self.assertEqual((len(rows),sum(x["amount"] for x in rows)),(count,total))
        self.assertEqual(len({x["row_id"] for x in self.staged["transactions"]}),len(self.staged["transactions"]))
        self.assertTrue(all(x["publication_status"]=="STAGING_ONLY" and
                            x["attendance_evidence"]=="NOT_ESTABLISHED" and
                            x["source_url"].startswith("https://www.police.go.kr/component/file/")
                            for x in reviewed))

    def test_no_attendee_inference_from_role(self):
        mutated=json.loads(json.dumps(self.staged))
        for x in mutated["transactions"]:
            x["attendance_evidence"]="CONFIRMED"
        d=review(mutated,self.manifest)
        self.assertEqual(d["staged_transaction_count"],0)
    def test_no_deduplication_by_date_and_amount(self):
        first=self.staged["transactions"][0]
        duplicated=dict(first,row_id="independent-original-row")
        d=review({"publication_enabled":False,"transactions":[first,duplicated]},self.manifest)
        self.assertEqual(d["staged_transaction_count"],2)
    def test_no_published_input(self):
        with self.assertRaises(ValueError):
            review({"publication_enabled":True,"transactions":[]},self.manifest)

if __name__=="__main__":unittest.main()
