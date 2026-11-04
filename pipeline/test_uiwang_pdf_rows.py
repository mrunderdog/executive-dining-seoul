"""Uiwang official 2026-08/09 PDF source-layout regressions.

Values below are direct row transcriptions from the sha256-verified
official source PDFs preserved in the live PDF evidence artifact.
"""
import unittest
from ingest_council_expense import normalize_uiwang_pdf_rows


def meta(month):
    return {
        "source": "uiwang", "region": "경기", "jurisdiction": "의왕시",
        "institution": "의왕시의회",
        "post_url": "https://council.uiwang.go.kr/kr/Information/bbsCost.do?reform=view",
        "attachment_url": "https://council.uiwang.go.kr/bbsAttachDownload.do?key=verified",
        "attachment_name": "의왕시의회.pdf", "period": (2026, month, None)
    }


class UiwangPdfRowsTests(unittest.TestCase):
    HEADER = ["일시", "집행내역", "금", "액", "지출처", "비 고"]

    def test_september_budget_chair_matches_official_subtotal(self):
        rows = [
            ["예결위원장 의회운영업무추진비 집행내역"],
            self.HEADER,
            ["9월 업무추진비"],
            ["2026. 9. 16. 18:54", "제322회 임시회 제6차 예산결산특별위원회 관련 간담",
             "104,700", "선일목장 정육식당", "예결위원장 등 6명"],
            ["2026. 9. 17. 16:42", "제322회 임시회 제7차 예산결산특별위원회 관련 간담",
             "149,000", "자담치킨 의왕부곡점", "예결위원장 등 22명"],
            ["253,700"],
        ]
        parsed, info = normalize_uiwang_pdf_rows(rows, "pdf-page-3", meta(9))
        self.assertEqual(info["status"], "OK")
        self.assertEqual(len(parsed), 2)
        self.assertEqual(sum(r["amount"] for r in parsed), 253700)
        self.assertTrue(all(r["role"] == "예결위원장" for r in parsed))
        self.assertEqual(parsed[0]["source_row"], 4)
        self.assertEqual(parsed[0]["used_date"], "2026-09-16")

    def test_september_office_expense_preserves_original_context(self):
        rows = [
            ["기관운영업무추진비 집행내역"], self.HEADER, ["9월 기관운영업무추진비"],
            ["2026. 9. 4. 16:49", "현안업무로 노고가 많은 소속직원 격려",
             "128,000", "멕시카나 의왕역점", "의회사무과장 등 14명"],
            ["128,000"],
        ]
        parsed, info = normalize_uiwang_pdf_rows(rows, "pdf-page-6", meta(9))
        self.assertEqual(info["status"], "OK")
        self.assertEqual(parsed[0]["role"], "기관운영업무추진비")
        self.assertEqual(parsed[0]["merchant"], "멕시카나 의왕역점")

    def test_august_official_semicolon_and_double_timestamps_preserved(self):
        rows = [
            ["의장 의회운영업무추진비 집행내역"], self.HEADER, ["8월 업무추진비"],
            ["2026. 8. 11. 12;21", "의전수행직원 노고 격려",
             "49,000", "월수금통돼지김치찌개(의왕오전점)", "서창수 의장 등 3명"],
            ["2026. 8. 19. 11:49, 12:26", "의회사무업무로 노고가 많은 소속 직원 격려",
             "271,000", "해물왕찜탕, 메가엠지씨커피 의왕오전점", "서창수 의장 등 12명"],
            ["320,000"],
        ]
        parsed, info = normalize_uiwang_pdf_rows(rows, "pdf-page-1", meta(8))
        self.assertEqual(info["status"], "OK")
        self.assertEqual([x["used_time"] for x in parsed], ["12;21", "11:49, 12:26"])
        self.assertEqual(parsed[1]["merchant"], "해물왕찜탕, 메가엠지씨커피 의왕오전점")

    def test_wrong_total_is_hold_not_success(self):
        rows = [
            ["의장 의회운영업무추진비 집행내역"], self.HEADER, ["9월 업무추진비"],
            ["2026. 9. 3. 12:32", "의회사무업무로 노고가 많은 소속 직원 격려",
             "224,500", "담가화로구이", "서창수 의장 등 7명"],
            ["224,600"],
        ]
        parsed, info = normalize_uiwang_pdf_rows(rows, "pdf-page-1", meta(9))
        self.assertEqual(len(parsed), 1)
        self.assertEqual(info["status"], "ROW_PARSE_GAPS")
        self.assertTrue(any(x["reason"] == "subtotal_mismatch_or_missing" for x in info["unparsed_examples"]))

    def test_unknown_page_or_missing_amount_is_hold(self):
        rows = [
            ["교섭단체 집행내역"], self.HEADER, ["8월 교섭단체"],
            ["2026. 8. 11. 13:36", "문화예술 발전 방안 관련 간담",
             "", "파스타입니다", "박재영 의원 등 2명"], ["25,800"],
        ]
        parsed, info = normalize_uiwang_pdf_rows(rows, "pdf-page-3", meta(8))
        self.assertEqual(parsed, [])
        self.assertEqual(info["status"], "ROW_PARSE_GAPS")

if __name__ == "__main__":
    unittest.main()
