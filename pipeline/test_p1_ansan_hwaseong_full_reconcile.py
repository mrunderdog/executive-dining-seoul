"""Proven original Ansan/Hwaseong XLSX cells: layout is not expenditure.

Monthly subtotals and explicit no-expense notices are accounted for as
non-transactions, not published as phantom venue records. Real cash support,
weekly-range expenses, and out-of-period originals must remain strict QA HOLD.
"""
import unittest
from ingest_council_expense import normalize_sheet
from qa_council_publication import period_bounds

META={"source":"ansan","region":"경기","jurisdiction":"안산시","institution":"안산시의회",
      "post_url":"https://www.ansan.go.kr/council/common/bbs/selectBbsDetail.do?bbs_code=B0406&bbs_seq=1668779",
      "attachment_url":"https://www.ansan.go.kr/common/file/FileDown.do?bbs_code=B0406&bbs_seq=1668779&file_id=17755428515161GYRGE27D0HWI7D8BAI257HVV",
      "attachment_name":"업무추진비 집행내역(2026년도 1분기).xlsx",
      "period":[2026,None,1],"default_role":"의장"}
HEADER=["사용자","사용일자","사용시간","사용장소","사용목적(내역)","사용금액(원)","대상인원(명)","결제방법"]

class AnsanOriginalStructuralCellTests(unittest.TestCase):
    def test_actual_monthly_count_and_total_are_not_fake_merchant(self):
        original=[HEADER,
                  ["의장","2026-01-30","21:00","싹쓰리 솥뚜껑 삼겹살","간담회",408000,12,"카드"],
                  ["1월 합계",None,None,"91건",12243770,"원",None,None],
                  ["의장","2026-02-02","12:35","색동면옥","간담회",63000,4,"카드"]]
        got,info=normalize_sheet(original,"의회(의회운영)",META)
        self.assertEqual(len(got),2,info)
        self.assertEqual([r["merchant"] for r in got],
                         ["싹쓰리 솥뚜껑 삼겹살","색동면옥"])
        self.assertEqual(info["structural_non_transaction_count"],1)
        note=info["structural_non_transaction_rows"][0]
        self.assertEqual(note["type"],"MONTHLY_AGGREGATE")
        self.assertEqual(note["source_cells"][3],"91건")
        self.assertEqual(note["source_cells"][4],"12243770")

    def test_actual_no_expenditure_note_is_not_a_transaction(self):
        raw=[HEADER,["내","역","없","음",None,None,None,None],
              ["2분기 총 계",None,None,None,None,0,None,None]]
        got,info=normalize_sheet(raw,"의회(정원가산)",{**META,"period":[2025,None,2]})
        self.assertEqual(got,[])
        self.assertEqual(info["structural_non_transaction_count"],1)
        self.assertEqual(info["structural_non_transaction_rows"][0]["type"],"NO_EXPENSE_NOTICE")

    def test_count_like_real_merchant_not_filtered_without_original_layout(self):
        raw=[HEADER,
             ["의장","2026-01-30","12:00","91건","실제 거래라고 기재된 행",35000,4,"카드"]]
        got,info=normalize_sheet(raw,"의회(의회운영)",META)
        self.assertEqual(len(got),1)
        self.assertEqual(info["structural_non_transaction_count"],0)

    def test_cash_without_place_is_still_an_unverified_spending_row(self):
        raw=[HEADER,["사무국장","2026-02-03","-",None,
                      "의회사무국 기관운영에 따른 경조사비 지급",100000,2,"현금"]]
        got,info=normalize_sheet(raw,"의회(기관운영)",META)
        self.assertEqual(len(got),1)
        self.assertEqual(got[0]["amount"],100000)
        self.assertEqual(got[0]["merchant"],"")
        self.assertEqual(info["structural_non_transaction_count"],0)

    def test_weekly_expense_range_not_rewritten_to_single_date(self):
        raw=[HEADER,["공통","24.11.25.~11.29.","17:21",
                      "고봉민김밥","제294회 정례회 급량비(1주차)",200500,20,"카드"]]
        got,info=normalize_sheet(raw,"의정운영공통경비",{**META,"period":[2024,None,4]})
        self.assertEqual(len(got),1)
        self.assertEqual(got[0]["used_date"],"24.11.25.~11.29.")
        self.assertEqual(info["structural_non_transaction_count"],0)

class HwaseongUnresolvedSourceTests(unittest.TestCase):
    def test_april_transactions_inside_may_original_are_not_relabelled(self):
        meta={**META,"source":"hwaseong","institution":"화성특례시의회",
              "period":[2026,5,None]}
        header=["연번","사용자","집행일시","사용장소","집행내역","금액","인원","결제방법"]
        raw=[header,[29,"경제환경위원장","2026-04-29 19:52","어부와명태",
                     "의정활동 자료수집 간담회 급식비",82000,4,"카드결제"]]
        got,info=normalize_sheet(raw,"의회운영업무추진비",meta)
        self.assertEqual(len(got),1,info)
        self.assertEqual(got[0]["used_date"],"2026-04-29")
        lo,hi=period_bounds(got[0]["source_period"])
        self.assertFalse(lo<=__import__("datetime").date.fromisoformat(got[0]["used_date"])<=hi)

if __name__=="__main__":
    unittest.main()
