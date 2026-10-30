"""Gimpo source-exception classification is complete, fail-closed and reproducible."""
import unittest
from reconcile_gimpo_sources import reconcile_gimpo, verify_gimpo_ledger
from ingest_council_expense import normalize_sheet

def row(rid, date, period, merchant, purpose, amount=50000, method="카드", file="file-q3",
        sheet="의회운영", time="12:16",role="의회운영위원장"):
    return {"row_id":rid,"institution":"김포시의회","source_key":"gimpo",
            "source_post_url":"https://gimpocouncil.go.kr/cnts/bbs/infoView.php?bbsCd=act&bbsSn=101",
            "source_attachment_url":file,"source_sheet":sheet,"source_row":5,
            "source_period":period,"used_date":date,"used_time":time,
            "role":role,"merchant":merchant,"purpose":purpose,
            "amount":amount,"people":3,"payment_method":method}

class GimpoSourceReconcileTests(unittest.TestCase):
    def test_2025_september_in_q4_must_match_genuine_q3(self):
        q3=row("q3","2025-09-02",[2025,None,3],"해물꽃돈","급식비 지급",57000)
        q4={**q3,"row_id":"q4","source_period":[2025,None,4],"source_attachment_url":"file-q4"}
        publish,ledger=reconcile_gimpo([q4,q3])
        self.assertEqual([x["row_id"] for x in publish],["q3"])
        self.assertEqual(ledger[0]["disposition"],"EXACT_CROSS_FILE_DUPLICATE")
        self.assertEqual(ledger[0]["evidence_matching_in_period_row"]["row_id"],"q3")
        docs=[{"url":"file-q3"},{"url":"file-q4"}]
        report={"source":"gimpo","files":docs,"rows":publish,"official_exception_ledger":ledger,
                "official_source_accounting":{"source_parsed_rows":2,"included_rows":1,
                    "exception_rows":1,
                    "exception_reason_counts":{"EXACT_CROSS_FILE_DUPLICATE":1}}}
        self.assertEqual(verify_gimpo_ledger(report),[])
        broken={**report,"official_source_accounting":{**report["official_source_accounting"],"source_parsed_rows":1}}
        self.assertIn("source_row_count_not_reconciled",verify_gimpo_ledger(broken))

    def test_mismatched_amount_cannot_be_declared_duplicate(self):
        good=row("q3","2025-09-02",[2025,None,3],"해물꽃돈","급식비 지급",57000)
        suspicious={**good,"row_id":"q4","source_period":[2025,None,4],
                    "source_attachment_url":"file-q4","amount":58000}
        published,exceptions=reconcile_gimpo([good,suspicious])
        self.assertEqual(len(published),1)
        self.assertEqual(exceptions[0]["disposition"],"HOLD_SOURCE_PERIOD")

    def test_cash_condolences_are_not_restaurants_but_unknown_cards_stay_hold(self):
        condolences=row("cash","2026-05-30",[2026,None,2],"","시의회 소속직원 축의금 지급(의장)",50000,"현금")
        unknown=row("unknown","2025-08-08",[2025,None,3],"","",54800,"카드")
        published,excluded=reconcile_gimpo([condolences,unknown])
        self.assertEqual(published,[])
        self.assertEqual([x["disposition"] for x in excluded],
            ["NON_DINING_CASH_SUPPORT","HOLD_UNIDENTIFIED_PLACE"])
        r={"source":"gimpo","rows":[],"files":[{"url":"file-q3"}],
            "official_exception_ledger":excluded,
            "official_source_accounting":{"source_parsed_rows":2,"included_rows":0,
              "exception_rows":2,"exception_reason_counts":{"NON_DINING_CASH_SUPPORT":1,"HOLD_UNIDENTIFIED_PLACE":1}}}
        self.assertIn("unresolved_official_transaction_exception",verify_gimpo_ledger(r))

    def test_q1_april_cafe_keeps_printed_date_and_holds(self):
        suspect=row("april","2026-04-06",[2026,None,1],"카페모임","음료비 지급",13400)
        accepted,ledger=reconcile_gimpo([suspect])
        self.assertFalse(accepted)
        self.assertEqual(ledger[0]["disposition"],"HOLD_SOURCE_PERIOD")

    def test_gimpo_exact_purpose_is_captured_instead_of_blank(self):
        cells=[
            ["연번","사용자","집행일시","사용장소","집행내역","집행대상","인원","금액","결제방법"],
            [1,"의회운영위원장","2025.09.02. 12:16","해물꽃돈",
                "소속 직원 업무추진 격려 급식비 지급(의회운영위원장)",
                "소속상근직원",3,57000,"카드"]]
        meta={"source":"gimpo","region":"경기","jurisdiction":"김포시","institution":"김포시의회",
             "post_url":"verified-post","attachment_url":"verified-file",
             "attachment_name":"공식분기자료.xlsx","period":[2025,None,3]}
        parsed,info=normalize_sheet(cells,"의회운영",meta)
        self.assertEqual(parsed[0]["purpose"],cells[1][4])
        self.assertEqual(info["mapping"]["purpose"],4)

if __name__=="__main__":unittest.main()
