"""Fail-closed, immutable Uiwang old-PDF replay tests."""
import copy
import hashlib
import unittest

from replay_failed_uiwang_pdfs import replay

URL = "https://council.uiwang.go.kr/bbsAttachDownload.do?key=" + "a" * 64
POST = "https://council.uiwang.go.kr/kr/Information/bbsCost.do?reform=view&key=" + "b" * 64
PDF = b"%PDF-1.4\n" + b"x" * 128
DIGEST = hashlib.sha256(PDF).hexdigest()
PERIOD = [2026, 8, None]
BASE = {
    "source": "uiwang", "rows": [{
        "row_id": "old-row", "source_key": "uiwang", "used_date": "2026-07-01",
        "merchant": "원본식당", "amount": 10000, "source_period": [2026, 7, None]}],
    "files": [{"url": URL, "sha256": DIGEST, "bytes": len(PDF),
               "name": "8월 의회운영업무추진비 사용내역.pdf",
               "sheets": [{"sheet": "pdf-page-1", "status": "NO_HEADER"}]}],
}
DISCOVERY = {"posts": [{"source": "uiwang", "period": PERIOD, "post_url": POST,
                        "region": "경기", "jurisdiction": "의왕시", "institution": "의왕시의회",
                        "attachments": [{"url": URL, "text": "8월 의회운영업무추진비.pdf"}]}]}
HEADER = ["일시", "집행내역", "금 액", "지출처", "비 고"]
ROW = ["2026. 8. 3. 13:38", "의전수행직원 노고 격려", "49,000",
       "월수금통돼지김치찌개(의왕오전점)", "서창수 의장 등 3명"]


def fake_sheets(blob, filename):
    yield "pdf-page-1", [HEADER, ROW]


class ReprocessTests(unittest.TestCase):
    def run_replay(self, *, binary=PDF, sheets=fake_sheets, base=None, discovery=None):
        raw = copy.deepcopy(base if base is not None else BASE)
        old = copy.deepcopy(raw)
        report, rows = replay(
            "uiwang", raw, copy.deepcopy(discovery if discovery is not None else DISCOVERY),
            "2026-07", "2026-09",
            download=lambda url, referer: binary,
            read_sheets=sheets,
        )
        self.assertEqual(raw, old, "replay must never modify its baseline input")
        self.assertEqual(report["publish"], False)
        return report, rows

    def test_digest_matched_replay_stages_only_new_rows(self):
        result, rows = self.run_replay()
        self.assertEqual(result["status"], "READY_FOR_REVIEW", result)
        self.assertEqual(result["staged_new_rows"], 1)
        self.assertEqual(rows[0]["amount"], 49000)
        self.assertEqual(rows[0]["role"], "의장")
        self.assertEqual(rows[0]["source_attachment_url"], URL)
        self.assertEqual(result["integrity"]["old_rows"], 1)
        self.assertEqual(result["integrity"]["new_rows"], 1)
        self.assertEqual(result["integrity"]["changed_file_count"], 0)

    def test_changed_digest_fails_closed(self):
        result, rows = self.run_replay(binary=PDF+b"CHANGED")
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(rows, [])
        self.assertIn("official_attachment_sha256_changed", result["failures"])

    def test_bad_extracted_transaction_cannot_be_dropped(self):
        def broken(blob, name):
            yield "pdf-page-1", [HEADER, ROW, ["2026. 8. 5. 11:30"]]
        result, rows = self.run_replay(sheets=broken)
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("unresolved_pdf_page", result["failures"])
        self.assertEqual(len(rows), 1)

    def test_no_header_with_dated_rows_holds(self):
        def no_header(blob, name):
            yield "pdf-page-1", [["의장 업무추진비"], ROW]
        result, rows = self.run_replay(sheets=no_header)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(rows, [])
        self.assertIn("unresolved_pdf_page", result["failures"])

    def test_duplicate_existing_row_not_overwritten(self):
        same = copy.deepcopy(BASE)
        original = fake_sheets(PDF, "test")
        new, _ = None, None
        # The identical parsed row is now in old records; it must not be staged twice.
        from ingest_council_expense import normalize_sheet
        meta = {"source": "uiwang", "region": "경기", "jurisdiction": "의왕시",
                "institution": "의왕시의회", "post_url": POST,
                "attachment_url": URL, "attachment_name": BASE["files"][0]["name"], "period": PERIOD}
        parsed, _ = normalize_sheet([HEADER, ROW], "pdf-page-1", meta)
        same["rows"].append(parsed[0])
        result, rows = self.run_replay(base=same)
        self.assertEqual(result["status"], "READY_FOR_REVIEW", result)
        self.assertEqual(rows, [])
        self.assertEqual(result["integrity"]["changed_row_count"], 0)

    def test_undiscovered_attachment_remains_hold(self):
        discovery = copy.deepcopy(DISCOVERY)
        discovery["posts"][0]["attachments"].append({
            "url": "https://council.uiwang.go.kr/bbsAttachDownload.do?key=" + "c"*64})
        result, _ = self.run_replay(discovery=discovery)
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("official_attachment_missing_from_baseline", result["failures"])

    def test_other_institution_is_denied(self):
        with self.assertRaises(ValueError):
            replay("ansan", BASE, DISCOVERY, "2026-07", "2026-09",
                   download=lambda *_: PDF, read_sheets=fake_sheets)



class IndependentOfficialEvidenceTests(unittest.TestCase):
    def test_independently_verified_monthly_date_amount_ledger(self):
        from replay_failed_uiwang_pdfs import (
            independent_source_evidence_check, fnv1a_date_amount,
        )
        records = [
            {"used_date": "2026-08-03", "amount": 49000, "source_period": [2026, 8, None]},
            {"used_date": "2026-08-04", "amount": 416200, "source_period": [2026, 8, None]},
        ]
        evidence = {"files": []}
        for month in ("2026-07", "2026-08", "2026-09"):
            filtered = [r for r in records if r["source_period"][1] == int(month[-2:])]
            total = sum(r["amount"] for r in filtered)
            evidence["files"].append({
                "period": month, "transaction_count": len(filtered),
                "transaction_total_krw": total,
                "printed_section_totals_krw": [total],
                "transaction_date_amount_fnv1a32": fnv1a_date_amount(filtered),
            })
        # Empty months still count as official periods in the comparison.
        verdict = independent_source_evidence_check(records, evidence)
        self.assertEqual(verdict["status"], "HOLD")  # coverage requires all 3 months
        modified = [*records, {"used_date": "2026-07-03", "amount": 5000,
                               "source_period": [2026, 7, None]},
                    {"used_date": "2026-09-07", "amount": 6000,
                     "source_period": [2026, 9, None]}]
        for item in evidence["files"]:
            selected = [r for r in modified if r["source_period"][1] == int(item["period"][-2:])]
            item["transaction_count"] = len(selected)
            item["transaction_total_krw"] = sum(r["amount"] for r in selected)
            item["printed_section_totals_krw"] = [item["transaction_total_krw"]]
            item["transaction_date_amount_fnv1a32"] = fnv1a_date_amount(selected)
        good = independent_source_evidence_check(modified, evidence)
        self.assertEqual(good["status"], "PASS", good)
        modified[0]["amount"] = 49001
        bad = independent_source_evidence_check(modified, evidence)
        self.assertEqual(bad["status"], "HOLD")
        self.assertTrue(any("mismatch" in x for x in bad["failures"]))

    def test_multiple_merchants_and_nondining_flagged_without_splitting(self):
        from replay_failed_uiwang_pdfs import classify_review_flags
        rows = [
            {"row_id": "a", "merchant": "황금코다리, 손커피연구소",
             "purpose": "간담회", "amount": 287900},
            {"row_id": "b", "merchant": "백운인쇄기획사",
             "purpose": "의원 명함 제작", "amount": 165000},
            {"row_id": "c", "merchant": "구이마을",
             "purpose": "간담회", "amount": 55000},
        ]
        flags = classify_review_flags(rows)
        self.assertEqual(len(flags), 2)
        self.assertIn("MULTI_MERCHANT_SHARED_AMOUNT", flags[0]["flags"])
        self.assertIn("NON_DINING_MERCHANT_REVIEW", flags[1]["flags"])
        self.assertEqual(rows[0]["amount"], 287900)

if __name__ == "__main__":
    unittest.main()
