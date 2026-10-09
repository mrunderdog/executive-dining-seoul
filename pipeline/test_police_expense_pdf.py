import unittest
from police_expense_pdf import parse_expense_table

URL="https://www.police.go.kr/component/file/ND_fileDownload.do?q_fileSn=160315&q_fileId=923edce7-c7c0-4778-a281-69058f6836da"
HEADER=[
    ["사용자","일자","내 역(건수)","사용처 (상호)","금 액","대상인원 (명)","집행방법"],
    ["경무인사\n기획관","소 계","5건","","640,400","",""],
    [None,"2026-08-05","전국경찰직협 간담회","사조미가","228,000","5","카드"],
    [None,"2026-08-13","건축자문위원회 정기회의 간담회","퍼스트플로어","135,400","3","카드"],
    [None,"2026-08-20","경찰의날 준비 기획단 간담회","사조미가","90,000","3","카드"],
    [None,"2026-08-31","예결위 쟁점 대비 업무 간담회","퍼스트플로어","98,000","6","카드"],
    [None,"2026-08-31","행안위 전체회의 업무 간담회","풍요람","89,000",None,None]
]
class PolicePdfTableTests(unittest.TestCase):
    def test_real_pdf_table_layout(self):
        rows,info=parse_expense_table(HEADER,"경무인사기획관",URL,"a"*64)
        self.assertEqual(len(rows),5)
        self.assertEqual(info["amount_total"],640400)
        self.assertEqual(sorted({r["merchant"] for r in rows}),["사조미가","퍼스트플로어","풍요람"])
        self.assertEqual(sum(x["amount"] for x in rows if x["merchant"]=="사조미가"),318000)
        self.assertEqual(rows[-1]["people"],None)
        self.assertTrue(all(r["attendance_evidence"]=="NOT_ESTABLISHED" for r in rows))
        self.assertTrue(all(r["publication_status"]=="STAGING_ONLY" for r in rows))
    def test_official_deputy_pdf_uses_abbreviated_user_title(self):
        raw=[["","차장 업무추진비 집행내역(2026년 2월)",None,None,None,None,None],
            ["사용자","일자","내 역(건수)","사용처(상호)","금 액","대상인원(명)","집행방법"],
            ["차장","소 계","1건","","60,000","",""],
            [None,"2026-02-02","국무회의 사전 대비 간담회","남원추어탕","60,000","6","카드"]]
        rows,control=parse_expense_table(raw,"경찰청차장",URL,"b"*64)
        self.assertEqual(control["records"],1)
        self.assertEqual(rows[0]["role"],"경찰청차장")
        self.assertEqual(rows[0]["attendance_evidence"],"NOT_ESTABLISHED")
    def test_abbreviated_role_requires_exact_official_heading(self):
        raw=[["","차관 업무추진비 집행내역(2026년 2월)",None,None,None,None,None],
            ["사용자","일자","내 역","사용처","금 액","인원","방법"],
            ["차장","소 계","1건","","60,000","",""],
            [None,"2026-02-02","회의","남원추어탕","60,000","6","카드"]]
        with self.assertRaisesRegex(ValueError,"role not found"):
            parse_expense_table(raw,"경찰청차장",URL,"b"*64)
    def test_total_mismatch_fails_entire_pdf(self):
        bad=[list(x) for x in HEADER]
        bad[3][4]="135,500"
        with self.assertRaisesRegex(ValueError,"control mismatch"):
            parse_expense_table(bad,"경무인사기획관",URL,"a"*64)
    def test_role_mismatch_fails(self):
        with self.assertRaisesRegex(ValueError,"role not found"):
            parse_expense_table(HEADER,"경찰청차장",URL,"a"*64)
    def test_unauthorized_pdf_host_fails(self):
        with self.assertRaisesRegex(ValueError,"official domain"):
            parse_expense_table(HEADER,"경무인사기획관",URL.replace("police.go.kr","police.go.kr.evil.test"),"a"*64)

if __name__=="__main__":unittest.main()
