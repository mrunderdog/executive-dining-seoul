import unittest
from capital_backfill import canonical_attachment_url
from ingest_council_expense import _html_attachment_candidates

class AttachmentSafetyTests(unittest.TestCase):
    def test_html_wrapper_candidates(self):
        html=b'<a href="/kr/news/attach">fake</a><a href="#lg-download">fake</a><a href="/kr/news/bbsAttachDownload.do">empty</a><a href="/files/report.xlsx?seq=3">file</a>'
        self.assertEqual(_html_attachment_candidates("https://council.ddc.go.kr/kr/news/bbsCost.do",html),
                         ["https://council.ddc.go.kr/files/report.xlsx?seq=3"])

    def test_only_canonical_files(self):
        self.assertIsNone(canonical_attachment_url("https://council.ddc.go.kr/kr/news/attach"))
        self.assertIsNone(canonical_attachment_url("https://council.ddc.go.kr/kr/news/bbsCost.do#lg-download"))
        self.assertIsNotNone(canonical_attachment_url("https://council.ddc.go.kr/kr/news/bbsAttachDownload.do?key=abc"))
if __name__=="__main__":unittest.main()
