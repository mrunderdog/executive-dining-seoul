"""Official Incheon Council PDF row fixtures: fail closed, no money inference."""
import unittest
from ingest_council_expense import normalize_sheet

FILE="https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&fileno=1&msg_seq=1320"
META={
    "source":"incheon_council","region":"인천","jurisdiction":"인천광역시",
    "institution":"인천광역시의회","post_url":"https://www.icouncil.go.kr/main/bbs/bbsMsgDetail.do?msg_seq=1320&bcd=infordisc",
    "attachment_url":FILE,"attachment_name":"2026년 8월 환경교통위원장 업무추진비 집행내역.pdf",
    "period":[2026,8,None],"default_role":"환경교통위원장",
    "attachment_sha256":"d85541d349a5f5e20fb4023be5c34093ad59a7e80483a3409af2c61143ef6dcb",
}
HEADER=["사 용 일 시", "집   행   목   적", "대상인원", "금   액", "장   소", "결제방법"]


class IncheonOriginalPdfFixtures(unittest.TestCase):
    def test_observed_aug31_25500_not_guessed(self):
        rows=[
            HEADER,
            ["2026-08-28 21:37 고령운전자 교통사고 예방 논의를 위한 간담회비 지출 3 43,000 한결통아구찜 인천효성점카드"],
            ["2026-08-31 18:37 온실가스 감축목표 달성 방안 논의를 위한 간담회비 지출 2 25,500 본죽&비빔밥 인천서해구청점카드"],
        ]
        rec,meta=normalize_sheet(rows,"pdf-page-2",META)
        self.assertEqual(meta["status"],"OK",meta)
        self.assertEqual(len(rec),2,meta)
        self.assertEqual(rec[1]["used_date"],"2026-08-31")
        self.assertEqual(rec[1]["used_time"],"18:37")
        self.assertEqual(rec[1]["amount"],25500)
        self.assertEqual(rec[1]["merchant"],"본죽&비빔밥 인천서해구청점")
        self.assertFalse(rec[1]["amount_inferred_from_row"])

    def test_missing_amount_is_hold_not_fabricated(self):
        rows=[HEADER,["2026-08-31 18:37 온실가스 감축목표 달성 방안 논의를 위한 간담회비 지출 2 본죽&비빔밥 인천서해구청점카드"]]
        rec,info=normalize_sheet(rows,"pdf-page-2",META)
        self.assertEqual(rec,[])
        self.assertEqual(info["status"],"ROW_PARSE_GAPS")
        self.assertEqual(info["unparsed_transaction_like_rows"],1)

    def test_official_september_operations_and_urban(self):
        cases=[
            (1326,"의회운영위원장",
             "일  자 시간 적   요 집행대상 금   액 장   소 지출방법",
             "2026-09-01 18:11 시의회 현안사항 논의를 위한 간담회비 지출 의회운영위원장 등 20명 231,900 신의주찹쌀순대(인천시청점) 카드",
             231900,"신의주찹쌀순대(인천시청점)"),
            (1322,"도시건설위원장",
             "사 용 일 시 집 행 목 적 대상인원 금 액 장 소 결제방법",
             "2026.09.03. 19:36 인천광역시 건축조례안 개정 논의 관련 의회운영업무추진비 지출 10 416,000 무이 스시 카드",
             416000,"무이 스시"),
            (1327,"환경교통위원장",
             "사 용 일 시 집 행 목 적 대상인원 금 액 장 소 결제방법",
             "2026-09-17 18:10 안전하고 쾌적한 생활하천 조성 논의를 위한 간담회비 지출 6 109,000 설화생갈비 카드",
             109000,"설화생갈비"),
        ]
        for seq,role,head,text,amount,merchant in cases:
            with self.subTest(seq=seq):
                meta={**META,"attachment_url":FILE.replace("1320",str(seq)),
                      "default_role":role}
                parsed,info=normalize_sheet([[head],[text]],"pdf-page-1",meta)
                self.assertEqual(info["status"],"OK",info)
                self.assertEqual(len(parsed),1)
                self.assertEqual(parsed[0]["amount"],amount)
                self.assertEqual(parsed[0]["merchant"],merchant)

    def test_official_page_two_without_repeated_header_uses_digest_pin(self):
        row=["2026-08-31 18:37온실가스 감축목표 달성 방안 논의를 위한 간담회비 지출", "2", "25,500본죽&비빔밥 인천서해구청점카드"]
        meta={**META, "attachment_sha256":"d85541d349a5f5e20fb4023be5c34093ad59a7e80483a3409af2c61143ef6dcb"}
        parsed,info=normalize_sheet([row], "pdf-page-2", meta)
        self.assertEqual(info["status"],"OK",info)
        self.assertEqual(parsed[0]["amount"],25500)
        bad={**meta,"attachment_sha256":"0"*64}
        parsed2,info2=normalize_sheet([row],"pdf-page-2",bad)
        self.assertEqual(parsed2,[])
        self.assertEqual(info2["status"],"OFFICIAL_SOURCE_SHA_CHANGED")

    def test_education_payee_from_official_column(self):
        meta={**META,"attachment_url":FILE.replace("1320","1323"),
              "default_role":"교육위원장",
              "attachment_sha256":"860248268daf693651bff18e8a3c737acbeb7d123e09629f041ac4540e0d21e8"}
        rows=[["일자","일시","적요","채주","대상","금액","집행방법"],
              ["2026-09-16","13:46","전문위원실 직원 격려 간담회 실시",
               "애플크로스","교육위원장등10명","121,500","카드"],
              ["2026-09-17","20:41","제313회 임시회 회기 운영 관련 논의를 위한 교육위원회 위원 간담회 실시",
               "손선장 소래포구점","교육위원장등8명","200,000","카드"],
              ["계(2건)","321,500"]]
        parsed,info=normalize_sheet(rows,"pdf-page-1",meta)
        self.assertEqual(info["status"],"OK",info)
        self.assertEqual(len(parsed),2)
        self.assertEqual(sum(p["amount"] for p in parsed),321500)

    def test_missing_clearly_printed_amount_holds(self):
        rows=[HEADER,["2026-08-31 18:37온실가스 감축목표 달성 방안 논의를 위한 간담회비 지출", "2", "본죽&비빔밥 인천서해구청점카드"]]
        parsed,info=normalize_sheet(rows,"pdf-page-1",META)
        self.assertFalse(parsed)
        self.assertEqual(info["status"],"ROW_PARSE_GAPS")
        self.assertEqual(info["unparsed_transaction_like_rows"],1)

    def test_unrecognized_pdf_has_no_source_specific_inference(self):
        meta={**META,"attachment_url":FILE.replace("1320","1329")}
        _,info=normalize_sheet([HEADER,["2026-09-01 18:00 테스트 1 20,000 상호 카드"]],"pdf-page-1",meta)
        self.assertNotEqual(info.get("parser"),"incheon_datefirst_official_pdf_v1")

if __name__=="__main__":
    unittest.main()
