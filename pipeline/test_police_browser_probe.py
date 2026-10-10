"""Police attachment Chromium-probe safety tests; offline and fast."""
import unittest
from police_browser_probe import police_url,police_variants,pdf_metadata,targets,official_download_url,merge_existing_staging

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
    def test_official_attachment_api_only(self):
        detail="https://www.police.go.kr/user/bbs/BD_selectBbs.do?q_bbsCode=1025"
        accepted="/component/file/ND_fileDownload.do?q_fileSn=159650&q_fileId=a330edbf-8623-4f19-b4f0-6e276098dfbf"
        self.assertEqual(official_download_url(detail,accepted,"차장 집행내역.pdf"),
            "https://www.police.go.kr"+accepted)
        self.assertEqual(official_download_url(detail,accepted,"바로보기"),"")
        self.assertEqual(official_download_url(detail,"https://evil.test/component/file/ND_fileDownload.do?q_fileSn=159650&q_fileId=a330edbf-8623-4f19-b4f0-6e276098dfbf","foo.pdf"),"")
        self.assertEqual(official_download_url(detail,"/component/file/ND_fileDownload.do?q_fileSn=invalid&q_fileId=no","foo.pdf"),"")
    def test_fake_pdf_bytes_never_accepted(self):
        info=pdf_metadata(b"<html>Login Required</html>")
        self.assertEqual(info["format"],"NOT_PDF")
        self.assertNotIn("pages",info)
    def test_failed_refresh_keeps_previous_verified_staging(self):
        prior={"publication_enabled":False,"transactions":[{"row_id":"stable-a","source_url":"https://www.police.go.kr/component/file/ND_fileDownload.do?q_fileSn=159650",
            "pdf_sha256":"a"*64,"publication_status":"STAGING_ONLY","attendance_evidence":"NOT_ESTABLISHED","used_date":"2026-02-02"}]}
        out=merge_existing_staging(prior,[])
        self.assertEqual(out["transactions_count"],1)
        self.assertEqual(out["prior_staged_count"],1)
        self.assertEqual(out["new_verified_count"],0)
        newly={**prior["transactions"][0],"row_id":"stable-b","used_date":"2026-03-01"}
        combined=merge_existing_staging(prior,[newly])
        self.assertEqual(combined["transactions_count"],2)
        self.assertEqual(merge_existing_staging(combined,[newly])["transactions_count"],2)
    def test_invalid_old_staging_not_promoted(self):
        previous={"publication_enabled":False,"transactions":[{"row_id":"abc","source_url":"https://evil.example/file.pdf",
          "pdf_sha256":"bad","publication_status":"STAGING_ONLY","attendance_evidence":"NOT_ESTABLISHED"}]}
        self.assertEqual(merge_existing_staging(previous,[])["transactions_count"],0)
        with self.assertRaises(ValueError):
            merge_existing_staging({"publication_enabled":True,"transactions":[]},[])
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
