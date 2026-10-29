"""Official-file P1 forensic parser/QA fixtures: never mask absent rows."""
import unittest
from ingest_council_expense import normalize_sheet
from qa_council_publication import assess

POST="https://www.gpassem.go.kr/kr/operations2BBSview.do?uid=4F6130EFA9271881F247B27B3D74B44F"
FILE="https://www.gpassem.go.kr/kr/bbs/download.do?bbs_id=operations2&uid=5BC8D54696620D004A1487979CBC8076"
META={"source":"gapyeong","region":"경기","jurisdiction":"가평군","institution":"가평군의회",
      "post_url":POST,"attachment_url":FILE,"attachment_name":"2024-4분기.pdf",
      "period":[2024,None,4],"default_role":"의장"}
HEADER=[
    ["일련","사용일자","사용일시","집행목적","사용금액","장소","대상인원","결제방법","비고"],
    ["번호","","","","(원)","(가맹점명)","(명)"],
]
class OfficialGapyeongPDFTests(unittest.TestCase):
    def test_verbatim_joined_amount_and_merchant_are_separate(self):
        table=HEADER+[
            ["23","12/11","16:21","관내 유관기관","간담회","260,000항아리토방","10","신용카드"],
            ["24","12/17","15:08","의회사무과 직원 격려","181,500교촌치킨","18","신용카드"],
        ]
        records,info=normalize_sheet(table,"pdf-page-2",META)
        self.assertEqual(info["status"],"OK",info)
        self.assertEqual(info["parsed_rows"],2)
        self.assertEqual(records[0]["merchant"],"항아리토방")
        self.assertEqual(records[0]["amount"],260000)
        self.assertEqual(records[0]["used_date"],"2024-12-11")
        self.assertEqual(records[0]["purpose"],"관내 유관기관 간담회")
        self.assertEqual(records[0]["role"],"의장")
        self.assertEqual(records[1]["merchant"],"교촌치킨")
        self.assertEqual(records[1]["amount"],181500)

    def test_quarter_label_never_rewrites_september_into_q4(self):
        records,info=normalize_sheet(HEADER+[["1","09/02","12:24","의정업무지원 직원 격려",
                                             "50,000대성등나무집","5","신용카드"]],"pdf-page-1",META)
        self.assertEqual(records[0]["used_date"],"2024-09-02")
        self.assertEqual(info["status"],"OK")

    def test_failed_amount_format_is_a_visible_parse_gap(self):
        rows,info=normalize_sheet(HEADER+[["23","12/11","16:21","간담회","금액없음항아리토방","10","신용카드"]],
                                  "pdf-page-2",META)
        self.assertEqual(rows,[])
        self.assertEqual(info["status"],"ROW_PARSE_GAPS")
        self.assertEqual(info["unparsed_transaction_like_rows"],1)
        payload={"source":"gapyeong","files":[{"url":FILE,"sha256":"a"*64,"bytes":560,
                    "sheets":[info]}],"rows":[],"errors":[]}
        discovery={"posts":[{"source":"gapyeong","post_url":POST,"attachments":[{"url":FILE}]}]}
        verdict=assess("gapyeong",payload,discovery,min_rows=1)
        self.assertIn("official_gapyeong_pdf_unparsed_transaction_rows",verdict["failures"])
        self.assertEqual(verdict["status"],"HOLD")

if __name__=="__main__":
    unittest.main()
