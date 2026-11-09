"""Uiwang council printed-PDF fixture tests (official August/September 2026 lines).

Source: council.uiwang.go.kr/kr/Information/bbsCost.do
The fixture lines preserve actual published merchant, amount, date and remarks.
They are not a substitute for full PDF visual/file-SHA reconciliation.
"""
import unittest

from ingest_council_expense import normalize_sheet
from qa_council_publication import assess

POST = ("https://council.uiwang.go.kr/kr/Information/bbsCost.do?"
        "reform=view&key=6a5c357ad968690a83ec3672c8e7d46e312b6a681669cf0da4914185a77b152695a418bf21c0c165")
FILE = ("https://council.uiwang.go.kr/bbsAttachDownload.do?"
        "key=42b2c5366f2c05875cf874d5b459ee33bc9aed47fe9a14592bc85b3c52ef51f63a7b570c532bd8e1")
META = {"source": "uiwang", "region": "경기", "jurisdiction": "의왕시",
        "institution": "의왕시의회", "post_url": POST, "attachment_url": FILE,
        "attachment_name": "8월 의회운영업무추진비 사용내역_의왕시의회.pdf",
        "period": [2026, 8, None], "default_role": ""}
HEADER = ["일시", "집행내역", "금  액", "지출처", "비 고"]


class UiwangLeadershipPdfTests(unittest.TestCase):
    def test_official_august_chair_and_vice_chair_rows(self):
        rows = [
            HEADER,
            ["2026. 8. 3. 13:38", "의전수행직원 노고 격려", "49,000",
             "월수금통돼지김치찌개(의왕오전점)", "서창수 의장 등 3명"],
            ["2026. 8. 4. 21:12", "부곡동 지역현안 청취를 위한 간담", "416,200",
             "부곡역 돼지갈비", "김동국 부의장 등 13명"],
            ["2026. 8. 14. 14:06", "원활한 의정활동을 위하여 의원 명함 제작",
             "275,000", "백운인쇄기획사", ""],
        ]
        records, info = normalize_sheet(rows, "pdf-page-1", META)
        self.assertEqual(info["status"], "OK", info)
        self.assertEqual(len(records), 3, info)
        self.assertEqual(records[0]["used_date"], "2026-08-03")
        self.assertEqual(records[0]["merchant"], "월수금통돼지김치찌개(의왕오전점)")
        self.assertEqual(records[0]["amount"], 49000)
        self.assertEqual(records[0]["role"], "의장")
        self.assertEqual(records[0]["people"], 3)
        self.assertEqual(records[0]["source_note"], "서창수 의장 등 3명")
        self.assertEqual(records[1]["role"], "부의장")
        self.assertEqual(records[1]["amount"], 416200)
        self.assertEqual(records[1]["people"], 13)
        self.assertEqual(records[2]["role"], "")
        self.assertIsNone(records[2]["people"])
        self.assertEqual(records[2]["merchant"], "백운인쇄기획사")

    def test_split_header_is_reconstructed_without_merging_transaction_cells(self):
        rows = [
            ["일시", "집행내역", "금", "액", "지출처", "비", "고"],
            ["2026. 8. 11. 12:16", "효율적인 의회업무추진 논의를 위한 간담",
             "57,000", "능이옥", "의회사무과장 등 3명"],
        ]
        records, info = normalize_sheet(rows, "pdf-page-2", META)
        self.assertEqual(info["status"], "OK", info)
        self.assertEqual(info["parsed_rows"], 1)
        self.assertEqual(records[0]["merchant"], "능이옥")
        self.assertEqual(records[0]["amount"], 57000)

    def test_unresolved_dated_row_is_visible_parse_gap(self):
        rows = [
            HEADER,
            ["2026. 8. 3. 13:38", "의전수행직원 노고 격려", "49,000",
             "월수금통돼지김치찌개(의왕오전점)", "서창수 의장 등 3명"],
            ["2026. 8. 4. 21:12"],
        ]
        records, info = normalize_sheet(rows, "pdf-page-1", META)
        self.assertEqual(len(records), 1)
        self.assertEqual(info["status"], "ROW_PARSE_GAPS")
        self.assertEqual(info["unparsed_transaction_like_rows"], 1)
        self.assertEqual(info["unparsed_source_rows"], [3])

    def test_missing_header_with_expenses_is_not_success(self):
        records, info = normalize_sheet(
            [["의장 의회운영업무추진비 집행내역"],
             ["2026. 8. 3. 13:38", "49,000", "월수금통돼지김치찌개"]],
            "pdf-page-1", META)
        self.assertEqual(records, [])
        self.assertEqual(info["status"], "ROW_PARSE_GAPS")
        self.assertEqual(info["unparsed_transaction_like_rows"], 1)

    def test_pdf_parse_gap_blocks_publication(self):
        data = {"source": "uiwang", "rows": [], "errors": [],
                "files": [{"url": FILE, "sha256": "a" * 64, "bytes": 1000,
                           "sheets": [{"sheet": "pdf-page-1",
                                       "status": "ROW_PARSE_GAPS",
                                       "unparsed_transaction_like_rows": 1}]}]}
        discovery = {"posts": [{"source": "uiwang", "post_url": POST,
                                "attachments": [{"url": FILE}]}]}
        verdict = assess("uiwang", data, discovery, min_rows=0)
        self.assertEqual(verdict["status"], "HOLD")
        self.assertIn("official_uiwang_pdf_unparsed_transaction_rows", verdict["failures"])


if __name__ == "__main__":
    unittest.main()
