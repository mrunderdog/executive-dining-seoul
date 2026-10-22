import json
import unittest
from pathlib import Path
from audit_council_payment_locations import ROOT, PRIORITIES, SOURCES, build, scan_source

class CouncilPaymentLocationTests(unittest.TestCase):
    def test_committed_audit_reproduces_verbatim(self):
        saved=json.loads((ROOT/"reports/council-payment-location-audit.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, build())
        self.assertEqual(saved["totals"]["confirmed_payment_branches"],0)
        self.assertEqual(set(x["source"] for x in saved["sources"]),set(SOURCES))

    def test_target_rows_trace_back_to_official_sources(self):
        for source in SOURCES:
            raw=json.loads((ROOT/"data/raw"/f"{source}_expense.json").read_text(encoding="utf-8"))
            rows={x["row_id"]:x for x in raw["rows"]}
            doc=scan_source(source)
            self.assertEqual(len(doc["priority_merchants"]),len(PRIORITIES[source]))
            for merchant in doc["priority_merchants"]:
                for tx in merchant["transactions"]:
                    original=rows[tx["row_id"]]
                    self.assertEqual(merchant["merchant"],original["merchant"])
                    self.assertEqual(tx["date"],original["used_date"])
                    self.assertEqual(tx["amount"],original["amount"])
                    self.assertEqual(tx["official_post_url"],original["source_post_url"])
                    self.assertEqual(tx["official_attachment_url"],original["source_attachment_url"])
                    self.assertEqual(merchant["payment_branch_status"],"NOT_VERIFIED")

    def test_no_directory_address_equated_to_card_payment_site(self):
        for source in SOURCES:
            doc=scan_source(source)
            self.assertGreater(doc["official_transactions"],0)
            self.assertEqual(doc["transactions_with_business_address"],0)
            self.assertEqual(doc["transactions_with_merchant_identifier"],0)
            self.assertEqual(doc["transactions_without_branch_evidence"],doc["official_transactions"])

if __name__=="__main__":
    unittest.main()
