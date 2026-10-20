import unittest
from copy import deepcopy
from unittest.mock import patch
from capital_backfill import canonical_attachment_url, title_period, council_js_posts, discover_source, ansan_file_attachments, Source, SOURCES
from ingest_council_expense import _html_attachment_candidates
from qa_council_publication import assess, assess_incremental

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
        listing="""<tr><td><a href="javascript:goViewPage('40957');">2026년 9월 화성시의회 업무추진비 내역</a></td></tr>"""
        detail="""<a href="javascript:fileDownLoad('30759','cns08');">사용내역(2026년 9월).xlsx</a>"""
        with patch("capital_backfill.fetch_text",side_effect=lambda u: detail if "boardView" in u else listing):
            result=discover_source(src,(2026,7),(2026,10))
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["attachments"][0]["url"],
             "https://council.hscity.go.kr/cms/utl/FileDownLoad.php?flCd=cns08&flSn=30759")

    def test_ansan_real_file_id_and_form_action(self):
        # Observed on the official 2026-Q3 page: #aform contains bbs_seq,
        # bbs_code and file_id, and fnFileDownLoad submits FileDown.do.
        url = "https://www.ansan.go.kr/council/common/bbs/selectBbsDetail.do?bbs_code=B0406&bbs_seq=1684397"
        detail = '''<ul class="p-attach"><li><a href="#" onclick="fnFileDownLoad('1791194526552UJ6PFYYEWJ7813RN8CIULM1NO'); return false;">
        <span class="p-icon p-icon__xlsx">xlsx 문서</span><span>업무추진비 집행내역(2026년도 3분기).xlsx</span></a>
        <a href="#" onclick="fnOpenPreview('1791194526552UJ6PFYYEWJ7813RN8CIULM1NO'); return false;">미리보기</a>
        <a href="#" onclick="fnFileDownLoad('nonsense'); return false;">bogus.xlsx</a></li></ul>'''
        found = ansan_file_attachments(url, detail)
        self.assertEqual(found, [{
            "text": "xlsx 문서 업무추진비 집행내역(2026년도 3분기).xlsx",
            "url": "https://www.ansan.go.kr/common/file/FileDown.do?bbs_code=B0406&bbs_seq=1684397&file_id=1791194526552UJ6PFYYEWJ7813RN8CIULM1NO",
        }])
        self.assertEqual(ansan_file_attachments("https://attacker.example/council/common/bbs/selectBbsDetail.do?bbs_code=B0406&bbs_seq=1684397",detail),[])
        src = next(s for s in SOURCES if s.key == "ansan")
        listing = "<tr><td><a onclick=\"fnGoDetail(1684397); return false;\">안산시의회 2026년도 3분기 업무추진비 집행내역 공개</a></td></tr>"
        with patch("capital_backfill.fetch_text", side_effect=lambda u: detail if "selectBbsDetail" in u else listing):
            discovered = discover_source(src, (2026, 7), (2026, 10))
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0]["attachments"], found)

    def test_quarter_periods(self):
        self.assertEqual(title_period("안산시의회 2026년도 3분기 업무추진비 집행내역"), (2026, None, 3))
        self.assertEqual(title_period("2026년 2/4분기 업무추진비"), (2026, None, 2))

    def test_publication_gate_rejects_bad_date_amount_and_file(self):
        post_url = "https://www.ansan.go.kr/council/common/bbs/selectBbsDetail.do?bbs_code=B0406&bbs_seq=1684397"
        file_url = "https://www.ansan.go.kr/common/file/FileDown.do?bbs_code=B0406&bbs_seq=1684397&file_id=1791194526552UJ6PFYYEWJ7813RN8CIULM1NO"
        discovery = {"posts": [{"source": "ansan", "post_url": post_url, "attachments": [{"url": file_url}]}]}
        good = {"source": "ansan", "files": [{"url": file_url, "sha256": "f" * 64, "bytes": 54670}], "rows": [{
            "source_key": "ansan", "source_post_url": post_url, "source_attachment_url": file_url,
            "source_period": [2026, None, 3], "used_date": "2026-08-20", "amount": 120_000,
            "merchant": "실제식당", "row_id": "unique1",
        }]}
        self.assertEqual(assess("ansan", good, discovery, 1)["status"], "PUBLISH_READY")
        for field, value in [("used_date", "2026-10-01"), ("used_date", "2026-08-32"),
                             ("amount", 0), ("amount", 500_000_000), ("merchant", "총계")]:
            bad = deepcopy(good)
            bad["rows"][0][field] = value
            self.assertEqual(assess("ansan", bad, discovery, 1)["status"], "HOLD", (field, value))
        bad = deepcopy(good)
        bad["files"] = []
        self.assertEqual(assess("ansan", bad, discovery, 1)["status"], "HOLD")
        bad = deepcopy(good)
        bad["errors"] = [{"url": file_url, "error": "file incomplete"}]
        self.assertEqual(assess("ansan", bad, discovery, 1)["status"], "HOLD")

    def test_incremental_gate_preserves_legacy_but_checks_every_changed_row(self):
        old_url = "https://www.ansan.go.kr/common/file/FileDown.do?file_id=old1"
        new_url = "https://www.ansan.go.kr/common/file/FileDown.do?file_id=new2"
        old_post, new_post = "https://www.ansan.go.kr/council/old", "https://www.ansan.go.kr/council/new"
        old_row = {
            "source_key": "ansan", "row_id": "legacy", "merchant": "기존식당",
            "source_post_url": old_post, "source_attachment_url": old_url,
            "source_period": [2026, None, 3], "used_date": "미상", "amount": None,
        }
        new_row = {
            "source_key": "ansan", "row_id": "fresh", "merchant": "새식당",
            "source_post_url": new_post, "source_attachment_url": new_url,
            "source_period": [2026, None, 3], "used_date": "2026-09-15", "amount": 120000,
        }
        old_file = {"url": old_url, "sha256": "f" * 64, "bytes": 1000}
        new_file = {"url": new_url, "sha256": "a" * 64, "bytes": 1000}
        baseline = {"source": "ansan", "rows": [old_row], "files": [old_file]}
        baseline_discovery = {"posts": [{"source": "ansan", "post_url": old_post,
                                         "attachments": [{"url": old_url}]}]}
        candidate = {"source": "ansan", "rows": [old_row, new_row], "files": [old_file, new_file]}
        discovery = {"posts": baseline_discovery["posts"] + [{"source": "ansan", "post_url": new_post,
                                                               "attachments": [{"url": new_url}]}]}
        ready = assess_incremental("ansan", candidate, discovery, baseline, baseline_discovery)
        self.assertEqual(ready["status"], "PUBLISH_READY")
        self.assertEqual(ready["verified_rows"], 1)
        self.assertEqual(ready["baseline_rows_preserved"], 1)
        self.assertEqual(assess_incremental("ansan", baseline, baseline_discovery,
                                            baseline, baseline_discovery)["status"], "NO_CHANGE")

        for field, value in [("amount", 0), ("used_date", "2026-10-01"), ("merchant", "합계")]:
            changed = deepcopy(candidate)
            changed["rows"][1][field] = value
            self.assertEqual(assess_incremental("ansan", changed, discovery,
                                                baseline, baseline_discovery)["status"], "HOLD", field)
        removed = deepcopy(candidate)
        removed["rows"] = [new_row]
        self.assertIn("historical_rows_removed", assess_incremental(
            "ansan", removed, discovery, baseline, baseline_discovery)["failures"])
        missing_file = deepcopy(candidate)
        missing_file["files"] = [old_file]
        self.assertEqual(assess_incremental("ansan", missing_file, discovery,
                                            baseline, baseline_discovery)["status"], "HOLD")
        orphan = deepcopy(candidate)
        orphan["rows"] = [old_row]
        self.assertEqual(assess_incremental("ansan", orphan, discovery,
                                            baseline, baseline_discovery)["status"], "HOLD")
        altered_historical_file = deepcopy(baseline)
        altered_historical_file["files"][0]["sha256"] = "b" * 64
        self.assertEqual(assess_incremental("ansan", altered_historical_file, baseline_discovery,
                                            baseline, baseline_discovery)["status"], "HOLD")
        self.assertEqual(assess_incremental("ansan", candidate, discovery, None, None)["status"],
                         "HOLD")  # Full first-publish gate also rejects the invalid legacy row.

    def test_only_canonical_files(self):
        self.assertIsNone(canonical_attachment_url("https://council.ddc.go.kr/kr/news/attach"))
        self.assertIsNone(canonical_attachment_url("javascript:fileDownLoad("))
        self.assertIsNone(canonical_attachment_url("https://council.hscity.go.kr/js/svc/filedownload.js?ver=2020707"))
        self.assertIsNone(canonical_attachment_url("https://council.ddc.go.kr/kr/news/bbsGalleryDownload.do"))
        self.assertIsNone(canonical_attachment_url("https://council.ddc.go.kr/kr/news/bbsCost.do#lg-download"))
        self.assertIsNotNone(canonical_attachment_url("https://council.ddc.go.kr/kr/news/bbsAttachDownload.do?key=abc"))
if __name__=="__main__":unittest.main()
