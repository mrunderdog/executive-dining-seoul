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
        self.assertEqual(d["staged_transaction_count"],20)
        self.assertEqual(sum(x["transactions"] for x in d["merchants"]),20)
        self.assertEqual(sum(x["amount_won"] for x in d["merchants"]),3691800)
        by={x["merchant"]:x for x in d["merchants"]}
        self.assertEqual(by["사조미가"]["status"],"VENUE_IDENTITY_APPROVED")
        self.assertEqual(by["사조미가"]["transactions"],2)
        self.assertEqual(by["남원추어탕"]["status"],"VENUE_LOCATION_NOT_VERIFIED")
        self.assertEqual(by["스타벅스코리아"]["status"],"NON_DINING_OR_GENERIC_BILLER")
        self.assertFalse(any(x["attendance_confirmed"] for x in d["merchants"]))
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
