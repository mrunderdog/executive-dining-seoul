"""Official-file P1 forensic parser/QA fixtures: never mask absent rows."""
import unittest
from ingest_council_expense import normalize_sheet
from qa_council_publication import assess, assess_incremental

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

    def test_gapyeong_missing_attendee_and_glued_payment_are_accounted_for(self):
        a=HEADER+[
            ["11","02/03","13:37","의회 내방객 음료 구입비",
             "718,300가평군청직장금고","신용카드"],
            ["12","02/05","12:05","전직 의원 간담회 개회",
             "48,000장가네","3신용카드"],
            ["13","02/06","21:02","집행부와의 업무협의 간담회",
             "186,000다한우","6신용카드"],
        ]
        rows, info=normalize_sheet(a,"pdf-page-6",META)
        self.assertEqual(info["status"],"OK",info)
        self.assertEqual(len(rows),3)
        self.assertEqual([r["merchant"] for r in rows],
                         ["가평군청직장금고","장가네","다한우"])
        self.assertEqual([r["people"] for r in rows],[None,3,6])

    def test_gapyeong_broken_number_must_never_be_invented(self):
        rows, info=normalize_sheet(HEADER+[
            ["7","03/19","10:46","화분 구입","350,00 0 꼬슬란","신용카드"]],
            "pdf-page-3",META)
        self.assertEqual(len(rows),0)
        self.assertEqual(info["unparsed_transaction_like_rows"],1)

    def test_2025_q4_split_first_serial_with_actual_pdf_layout(self):
        meta={**META,"period":[2025,None,4]}
        # Observed PyPDF page header prints first ordinal in a separate cell.
        rows=HEADER+[["1"],["10/13","14:43","북면 생활개선회 의견청취 간담회",
                            "132,000도니우니정육점","5","신용카드"]]
        parsed,info=normalize_sheet(rows,"pdf-page-1",meta)
        self.assertEqual(info["status"],"OK",info)
        self.assertEqual(len(parsed),1)
        self.assertEqual(parsed[0]["amount"],132000)
        self.assertEqual(parsed[0]["merchant"],"도니우니정육점")
        self.assertEqual(info["verified_first_serial_splits"][0]["printed_serial"],1)

    def test_visual_sha_bound_pdf_amount_repair(self):
        meta={**META,"period":[2026,None,1],
              "attachment_sha256":"5769afc384be8459893ad18bbd209b24e267e96f5dffaeee60d52c10dad7aea2"}
        row=["12","03/19","10:46","제336회 가평군의회 임시회 운영을 위한 환경정비 화분 구입",
             "350,00 0 꼬슬란","신용카드"]
        parsed,info=normalize_sheet(HEADER+[row],"pdf-page-6",meta)
        self.assertEqual(len(parsed),1,info)
        self.assertEqual(parsed[0]["amount"],350000)
        self.assertEqual(parsed[0]["merchant"],"꼬슬란")
        self.assertEqual(len(info["source_verified_currency_repairs"]),1)
        # The same string in any other official file MUST NOT be repaired.
        unauthorized,failed=normalize_sheet(HEADER+[row],"pdf-page-6",{**meta,"attachment_sha256":"a"*64})
        self.assertEqual(unauthorized,[])
        self.assertEqual(failed["status"],"ROW_PARSE_GAPS")

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

class IncrementalHistoricalSourceScope(unittest.TestCase):
    def test_committed_legacy_files_do_not_become_new_when_discovery_baseline_empty(self):
        base_url="https://council.icbp.go.kr/kr/news/bbs_process?reform=download&bbs_id=expense&uid=12345"
        new_url="https://council.icbp.go.kr/kr/news/bbs_process?reform=download&bbs_id=expense&uid=62747"
        old_post="https://council.icbp.go.kr/kr/news/bbs?bbs_id=expense&reform=view&uid=OLD"
        new_post="https://council.icbp.go.kr/kr/news/bbs?bbs_id=expense&reform=view&uid=NEW"
        legacy={"row_id":"past","source_key":"bupyeong","source_post_url":old_post,
                "source_attachment_url":base_url,"source_period":[2024,12,None],
                "used_date":"2024-01-02","merchant":"오래된 공식 기록",
                "amount":92000}
        new={"row_id":"now","source_key":"bupyeong","source_post_url":new_post,
             "source_attachment_url":new_url,"source_period":[2026,9,None],
             "used_date":"2026-09-15","merchant":"검증된 식당","amount":50000}
        oldfile={"url":base_url,"sha256":"a"*64,"bytes":900}
        newfile={"url":new_url,"sha256":"b"*64,"bytes":850}
        baseline={"source":"bupyeong","rows":[legacy],"files":[oldfile]}
        current={"source":"bupyeong","rows":[legacy,new],"files":[oldfile,newfile],"errors":[]}
        discovery={"posts":[
            {"source":"bupyeong","post_url":old_post,"attachments":[{"url":base_url}]},
            {"source":"bupyeong","post_url":new_post,"attachments":[{"url":new_url}]}]}
        result=assess_incremental("bupyeong",current,discovery,baseline,{"posts":[]})
        self.assertEqual(result["status"],"PUBLISH_READY",result)
        self.assertEqual(result["new_or_changed_rows"],1)
        self.assertEqual(result["verified_files"],1)
        self.assertEqual(result["verified_rows"],1)
        # If the *new* transaction date is outside its official period,
        # it must still fail the exact same strict QA.
        bad={**new,"used_date":"2026-08-15"}
        other=assess_incremental("bupyeong",{**current,"rows":[legacy,bad]},discovery,baseline,{"posts":[]})
        self.assertEqual(other["status"],"HOLD",other)
        self.assertIn("date_amount_or_lineage_invalid_rows",other["failures"])

if __name__=="__main__":
    unittest.main()
