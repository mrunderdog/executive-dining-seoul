"""Strict source-level QA tests for verified Incheon PDF pages."""
import unittest
from qa_council_publication import assess

URL="https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&fileno=1&msg_seq=1330"
POST="https://www.icouncil.go.kr/main/bbs/bbsMsgDetail.do?bcd=infordisc&msg_seq=1330"
ROW={
    "row_id":"confirmed-1","source_key":"incheon_council",
    "source_post_url":POST,"source_attachment_url":URL,
    "merchant":"경복궁구월점","amount":291000,
    "used_date":"2026-09-15","source_period":[2026,9,None]
}
BASE={
    "source":"incheon_council","rows":[ROW],
    "files":[{"url":URL,"sha256":"a958b2f26f025d100ba3c7d7310e434e21aad4c029d2fe6f4c0c9008e1a374e3",
              "bytes":15345,
              "sheets":[
                  {"sheet":"pdf-page-1","status":"DUPLICATE_OFFICIAL_PAGE_NO_NEW_ROWS","parsed_rows":0},
                  {"sheet":"pdf-page-2","status":"OK","parsed_rows":13}
              ]}]
}
DISC={"posts":[{"source":"incheon_council","post_url":POST,
               "attachments":[{"url":URL}]}]}

class IncheonReleaseQATests(unittest.TestCase):
    def test_certified_duplicate_page_is_not_a_second_13_transactions(self):
        result=assess("incheon_council",BASE,DISC,min_rows=1)
        self.assertEqual(result["status"],"PUBLISH_READY",result)
        self.assertEqual(result["verified_rows"],1)

    def test_hidden_pdf_transaction_gap_blocks_release(self):
        source={**BASE,"files":[{**BASE["files"][0],
          "sheets":[{"sheet":"pdf-page-1","status":"ROW_PARSE_GAPS",
                     "unparsed_transaction_like_rows":1}]}]}
        report=assess("incheon_council",source,DISC,min_rows=1)
        self.assertEqual(report["status"],"HOLD",report)
        self.assertIn("official_incheon_pdf_unparsed_or_unsupported_page",report["failures"])

    def test_duplicate_without_unique_certified_page_is_hold(self):
        source={**BASE,"files":[{**BASE["files"][0],
          "sheets":[{"sheet":"pdf-page-1",
                     "status":"DUPLICATE_OFFICIAL_PAGE_NO_NEW_ROWS","parsed_rows":0}]}]}
        report=assess("incheon_council",source,DISC,min_rows=1)
        self.assertEqual(report["status"],"HOLD",report)

if __name__=="__main__":
    unittest.main()
