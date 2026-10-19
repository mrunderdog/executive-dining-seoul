import unittest
from io import BytesIO
from unittest.mock import patch
from openpyxl import Workbook
from audit_official_source_address_fields import inspect_xlsx, inspect_doc, fetch, attachment_candidates

class AuditTests(unittest.TestCase):
    def test_exact_merchant_address_only_and_no_automatic_approval(self):
        w=Workbook();s=w.active;s.title="집행";s.append(["날짜","사용처","주소","액수"])
        s.append(["2026-01-01","동명이인식당","서울 중구 세종대로 12",10000])
        s.append(["2026-01-02","대상식당","서울 중구 세종대로 33",20000])
        s.append(["2026-01-03","대상식당","서울",10000])
        f=BytesIO();w.save(f)
        result=inspect_xlsx(f.getvalue(),{"대상식당"})
        self.assertEqual(len(result["matched_rows"]),1)
        row=result["matched_rows"][0]
        self.assertEqual(row["excel_row"],3)
        self.assertEqual(row["candidate_address"],"서울 중구 세종대로 33")
        self.assertFalse(row["payment_branch_verified"])
    def test_same_host_attachment_candidate_only(self):
        html='<a href="/files/records.xlsx"><span>업무추진비.xlsx</span></a><a href="https://evil.test/x.pdf">외부.pdf</a><a href="javascript:bad">bad.pdf</a>'
        actual=attachment_candidates(html,"https://www.kamco.or.kr/portal/bbs/view.do")
        self.assertEqual(actual,["https://www.kamco.or.kr/files/records.xlsx"])
        self.assertEqual(attachment_candidates(html,"https://evil.test/post"),[])

    def test_reject_unofficial_host(self):
        with self.assertRaises(ValueError):
            fetch("https://example.org/test.xlsx")
    def test_error_never_creates_evidence(self):
        with patch("audit_official_source_address_fields.fetch",side_effect=TimeoutError("no response")):
            r=inspect_doc("https://www.moj.go.kr/doc",{"대상식당"})
        self.assertEqual(r["status"],"FETCH_OR_PARSE_FAILED")
        self.assertEqual(r["exact_official_source_row_candidates"],[])

if __name__=="__main__":unittest.main()
