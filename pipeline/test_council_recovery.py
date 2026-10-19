import unittest
from unittest.mock import patch
from capital_backfill import canonical_attachment_url, title_period, council_js_posts, discover_source, Source, SOURCES
from ingest_council_expense import _html_attachment_candidates

class AttachmentSafetyTests(unittest.TestCase):
    def test_html_wrapper_candidates(self):
        html=b'<a href="/kr/news/attach">fake</a><a href="#lg-download">fake</a><a href="/kr/news/bbsAttachDownload.do">empty</a><a href="/files/report.xlsx?seq=3">file</a>'
        self.assertEqual(_html_attachment_candidates("https://council.ddc.go.kr/kr/news/bbsCost.do",html),
                         ["https://council.ddc.go.kr/files/report.xlsx?seq=3"])

    def test_real_council_click_identifiers(self):
        h='<tr><td><a href="javascript:goViewPage(\'40957\');">2026년 9월 화성시의회 업무추진비 및 공통경비 내역</a></td></tr>'
        hw=next(s for s in SOURCES if s.key=="hwaseong")
        out=council_js_posts(hw,"https://council.hscity.go.kr/cnts/bbs/boardList.php?bbsCd=cns&bbsSubCd=cns08",h,(2026,7),(2026,10))
        self.assertEqual(len(out),1)
        self.assertIn("bbsSn=40957",out[0]["post_url"])
        self.assertEqual(out[0]["period"],(2026,9,None))
        d='<tr><td><a href="#none" data-reform="view" data-key="'+("a"*72)+'">업무추진비 사용내역(2026년 9월)</a></td></tr>'
        dd=next(s for s in SOURCES if s.key=="dongducheon")
        out=council_js_posts(dd,"https://council.ddc.go.kr/kr/news/bbsCost.do?flag=all&page=1",d,(2026,7),(2026,10))
        self.assertEqual(len(out),1)
        self.assertIn("reform=view",out[0]["post_url"])
        self.assertIn("key="+("a"*72),out[0]["post_url"])
        self.assertEqual(title_period("2026년도 3분기 업무추진비"),(2026,None,3))
        a='<tr><td><a onclick="fnGoDetail( 1684397 ); return false;">안산시의회 2026년도 3분기 업무추진비 집행내역 공개</a></td></tr>'
        src=next(s for s in SOURCES if s.key=="ansan")
        out=council_js_posts(src,"https://www.ansan.go.kr/council/common/bbs/selectPageListBbs.do?bbs_code=B0406",a,(2026,7),(2026,10))
        self.assertEqual(len(out),1)
        self.assertIn("selectBbsDetail.do",out[0]["post_url"])
        self.assertIn("bbs_seq=1684397",out[0]["post_url"])

    def test_hwasung_official_file_download_params(self):
        from capital_backfill import fetch_text
        src=Source("hwaseong","경기","화성시","화성특례시의회",
                   "https://council.hscity.go.kr/cnts/bbs/boardList.php?bbsCd=cns&bbsSubCd=cns08&pageNo={page}",1,"monthly")
        listing="<tr><td><a href=\\\"javascript:goViewPage('40957');\\\">2026년 9월 화성시의회 업무추진비 내역</a></td></tr>"
        detail="<a href=\\\"javascript:fileDownLoad('30759','cns08');\\\">사용내역(2026년 9월).xlsx</a>"
        with patch("capital_backfill.fetch_text",side_effect=lambda u: detail if "boardView" in u else listing):
            result=discover_source(src,(2026,7),(2026,10))
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["attachments"][0]["url"],
             "https://council.hscity.go.kr/cms/utl/FileDownLoad.php?flSn=30759&flCd=cns08")

    def test_only_canonical_files(self):
        self.assertIsNone(canonical_attachment_url("https://council.ddc.go.kr/kr/news/attach"))
        self.assertIsNone(canonical_attachment_url("javascript:fileDownLoad("))
        self.assertIsNone(canonical_attachment_url("https://council.hscity.go.kr/js/svc/filedownload.js?ver=2020707"))
        self.assertIsNone(canonical_attachment_url("https://council.ddc.go.kr/kr/news/bbsGalleryDownload.do"))
        self.assertIsNone(canonical_attachment_url("https://council.ddc.go.kr/kr/news/bbsCost.do#lg-download"))
        self.assertIsNotNone(canonical_attachment_url("https://council.ddc.go.kr/kr/news/bbsAttachDownload.do?key=abc"))
if __name__=="__main__":unittest.main()
