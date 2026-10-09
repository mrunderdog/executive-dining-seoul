"""Police attachment Chromium-probe safety tests; offline and fast."""
import unittest
from police_browser_probe import police_url,police_variants,pdf_metadata,targets

class BrowserProbeContract(unittest.TestCase):
    def test_allowed_official_https_hosts_only(self):
        assert police_url("https://www.police.go.kr/user/bbs/BD_selectBbs.do")
        assert police_url("https://police.go.kr/user/bbs/BD_selectBbs.do")
        for u in (
            "http://www.police.go.kr/user/bbs/foo",
            "https://police.go.kr.evil.test/user/bbs/foo",
            "https://notpolice.go.kr/user/bbs/foo",
            "https://user:password@other.test/user/bbs/foo",
        ):
            self.assertFalse(police_url(u),u)
    def test_no_untrusted_redirect_targets_generated(self):
        url="https://www.police.go.kr/user/bbs/BD_selectBbs.do?q_bbsCode=1025"
        variants=police_variants(url)
        self.assertEqual(variants[0],url)
        self.assertGreaterEqual(len(variants),2)
        self.assertTrue(all(police_url(x) for x in variants))
        self.assertTrue(all("q_bbsCode=1025" in x for x in variants))
        self.assertEqual(police_variants("https://evil.test/user/bbs/x"),[])
    def test_fake_pdf_bytes_never_accepted(self):
        info=pdf_metadata(b"<html>Login Required</html>")
        self.assertEqual(info["format"],"NOT_PDF")
        self.assertNotIn("pages",info)
    def test_official_seed_selection_only(self):
        registry={"sources":[{"key":"national_police","verified_detail_urls":[
            {"title":"Police deputy budget","role":"경찰청차장",
             "url":"https://www.police.go.kr/user/bbs/BD_selectBbs.do?q_bbsCode=1025"},
            {"title":"Not official","role":"경찰청차장",
             "url":"https://police.go.kr.evil.test/download.pdf"}]}]}
        got=targets(registry)
        self.assertEqual(len(got),1)
        self.assertEqual(got[0]["role"],"경찰청차장")

if __name__=="__main__":unittest.main()
