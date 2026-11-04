"""Offline regressions for full official file/cell evidence, including failures."""
import json
import tempfile
import unittest
from pathlib import Path
from incheon_source_capture import OriginalSourceCapture, match_invalid_rows


class IncheonSourceCaptureTests(unittest.TestCase):
    def test_bad_amount_retains_exact_original_cells_and_lineage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source-capture.json"
            c = OriginalSourceCapture("incheon_council", path)
            post = {"post_url": "https://www.icouncil.go.kr/main/bbs/bbsMsgDetail.do?msg_seq=1318",
                    "title": "2026년 8월 행정안전위원장", "period": [2026, 8, None]}
            file = c.start(post, "https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?msg_seq=1318", "original.pdf")
            c.downloaded(file, b"%PDF official", "a" * 64)
            sheet = c.sheet(file, "pdf-page-2", [
                ["일자", "금액", "장소"],
                ["2026-08-31", "", "가게A"],
            ])
            bad = {"row_id": "e6256a2ab172f5fd2ac7", "source_row": 2,
                   "source_sheet": "pdf-page-2", "used_date": "2026-08-31",
                   "merchant": "가게A", "amount": None,
                   "source_attachment_url": file["attachment_url"]}
            c.normalized(file, sheet, [bad], {"status": "OK"})
            c.succeeded(file)
            c.write()
            loaded = json.loads(path.read_text(encoding="utf-8"))
            result = match_invalid_rows(loaded, [bad["row_id"]])
            self.assertFalse(result["invalid_row_ids_missing_original_cells"])
            found = result["invalid_row_evidence"][bad["row_id"]][0]
            self.assertEqual(found["source_row"], 2)
            self.assertEqual(found["source_sheet"], "pdf-page-2")
            self.assertEqual(found["original_source_cells"][1]["value"], "")
            self.assertEqual(found["normalized_row"]["amount"], None)
            self.assertEqual(found["attachment_sha256"], "a" * 64)

    def test_failed_download_or_parser_is_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source-capture.json"
            c = OriginalSourceCapture("incheon_council", path)
            e = c.start({"post_url": "official-post", "title": "document", "period": [2026, 8, None]},
                        "official-file", "file.pdf")
            c.failed(e, TimeoutError("official upstream timeout"))
            c.write()
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["attachment_errors"]), 1)
            self.assertEqual(data["attachment_errors"][0]["failed_phase"], "download")
            self.assertIn("TimeoutError", data["attachment_errors"][0]["error"])
            self.assertEqual(data["status"], "COMPLETE_WITH_ERRORS")

    def test_unavailable_source_address_is_explicit(self):
        missing = match_invalid_rows({"files": [], "attachment_errors": []}, ["missing-id"])
        self.assertEqual(missing["invalid_row_ids_missing_original_cells"], ["missing-id"])
        self.assertEqual(missing["invalid_row_evidence"]["missing-id"], [])

    def test_sheet_failure_retains_raw_cells_even_without_normalized_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = OriginalSourceCapture("incheon_council", Path(tmp) / "source-capture.json")
            e = c.start({"post_url": "official-post", "period": [2026, 8, None]}, "official-file", "source.pdf")
            c.downloaded(e, b"%PDF", "b" * 64)
            c.sheet(e, "pdf-page-3", [["2026-08-31", "original amount not parseable"]])
            c.failed(e, ValueError("unparsed page"))
            c.write()
            out = json.loads(c.destination.read_text(encoding="utf-8"))
            self.assertEqual(out["files"][0]["sheets"][0]["raw_source_rows"][0]["source_row"], 1)
            self.assertEqual(out["attachment_errors"][0]["recorded_sheets"], ["pdf-page-3"])


    def test_inflight_http_request_is_checkpointed_before_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.json"
            c = OriginalSourceCapture("incheon_council", p)
            e = c.start({"post_url": "official-post", "period": [2026, 8, None]},
                        "https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?msg_seq=1324",
                        "source.pdf")
            snapshot = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["status"], "INCOMPLETE")
            self.assertEqual(snapshot["files"][0]["status"], "FETCH_STARTED")
            self.assertEqual(snapshot["files"][0]["attachment_url"], e["attachment_url"])
            self.assertFalse(snapshot["publication_authorized"])

    def test_incheon_direct_download_bounded_no_detail_warmup(self):
        import urllib.error
        from unittest.mock import patch, MagicMock
        from ingest_council_expense import fetch_binary
        url = ("https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do"
               "?bcd=infordisc&fileno=1&msg_seq=1324")
        post = "https://www.icouncil.go.kr/main/bbs/bbsMsgDetail.do?msg_seq=1324"
        mock_opener = MagicMock()
        mock_opener.open.side_effect = urllib.error.URLError("official timeout")
        with patch("ingest_council_expense.urllib.request.build_opener",
                   return_value=mock_opener):
            with self.assertRaises(urllib.error.URLError):
                fetch_binary(url, post)
        self.assertEqual(mock_opener.open.call_count, 1)
        self.assertEqual(mock_opener.open.call_args.kwargs["timeout"], 12)

if __name__ == "__main__":
    unittest.main()
