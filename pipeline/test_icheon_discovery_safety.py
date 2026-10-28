"""Deterministic regression fixtures: Icheon partial discoveries never replace last-good."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import capital_backfill as cb
from diagnose_icheon import run as diagnostic
from qa_council_publication import assess_incremental

POST="https://council.icheon.go.kr/content/information/businessOperatingExpense.html?fidx=6005&pg=vv"
OLD="https://council.icheon.go.kr/gtb_download.php?fid=4893&gtid=chujin"
NEW1="https://council.icheon.go.kr/gtb_download.php?fid=4999&gtid=chujin"
NEW2="https://council.icheon.go.kr/gtb_download.php?fid=5000&gtid=chujin"

def post(urls, title="2026년 9월 이천시의회 업무추진비"):
    return {"source":"icheon","title":title,"period":[2026,9,None],"post_url":POST,
            "attachments":[{"url":u,"text":"업무추진비.pdf"} for u in urls]}

class IcheonSafety(unittest.TestCase):
    def test_valid_live_discovery_is_accepted(self):
        d=cb.icheon_discovery_issues([post([OLD,NEW1])],{"posts":[post([OLD])]},(2026,6),(2026,10))
        self.assertEqual(d["status"],"OK",d)

    def test_missing_previous_attachment_triggers_degraded(self):
        d=cb.icheon_discovery_issues([post([NEW1])],{"posts":[post([OLD])]},(2026,6),(2026,10))
        self.assertIn("prior_verified_attachments_missing",d["problems"])
        self.assertEqual(d["missing_prior_attachment_urls"],[OLD])

    def test_failed_new_post_detail_does_not_look_like_complete_discovery(self):
        damaged={**post([]),"post_url":POST+"&broken=1","error":"detail TimeoutExpired: timed out"}
        d=cb.icheon_discovery_issues([post([OLD]),damaged],{"posts":[post([OLD])]},(2026,6),(2026,10))
        self.assertIn("current_listing_or_detail_error",d["problems"])

    def test_verified_seed_only_is_not_a_live_success(self):
        fallback={**post([OLD]),"recovery_trigger":"no_current_downloadable_posts",
                  "discovery_method":"historically_verified_ids_revalidate_pdf"}
        d=cb.icheon_discovery_issues([fallback],{"posts":[post([OLD])]},(2026,6),(2026,10))
        self.assertIn("fallback_not_live_discovery",d["problems"])

    def test_missing_old_attachment_outside_requested_period_does_not_block(self):
        historical={**post([OLD]),"period":[2025,1,None]}
        d=cb.icheon_discovery_issues([post([NEW1])],{"posts":[historical]},(2026,6),(2026,10))
        self.assertEqual(d["status"],"OK",d)

    def test_partial_discovery_main_keeps_last_good_file_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            reports=Path(tmp)
            existing={"posts":[post([OLD])],"generated_at":"before"}
            file=reports/"capital-backfill-discovery-icheon.json"
            original=json.dumps(existing,ensure_ascii=False)
            file.write_text(original,encoding="utf-8")
            failure={**post([]),"error":"detail URLError: transient"}
            with (patch.object(cb,"REPORTS",reports),
                  patch.object(cb,"discover_source",return_value=[post([OLD]),failure]),
                  patch.object(sys,"argv",["capital_backfill.py","--source","icheon","--since","2026-06","--until","2026-10"]),
                  contextlib.redirect_stdout(io.StringIO())):
                with self.assertRaises(SystemExit) as caught: cb.main()
            self.assertEqual(caught.exception.code,2)
            self.assertEqual(file.read_text(encoding="utf-8"),original)

    def test_unlinked_new_pdf_is_held_even_if_other_pdf_has_transactions(self):
        oldrow={"row_id":"old","source_key":"icheon","source_attachment_url":OLD,
                "source_post_url":POST,"merchant":"기존식당","used_date":"2026-09-01","amount":100000,
                "source_period":[2026,9,None]}
        newrow={"row_id":"fresh","source_key":"icheon","source_attachment_url":NEW1,
                "source_post_url":POST,"merchant":"새식당","used_date":"2026-09-15","amount":120000,
                "source_period":[2026,9,None]}
        oldfile={"url":OLD,"sha256":"f"*64,"bytes":1000}
        addedfile1={"url":NEW1,"sha256":"a"*64,"bytes":1000}
        addedfile2={"url":NEW2,"sha256":"b"*64,"bytes":1000}
        old={"source":"icheon","files":[oldfile],"rows":[oldrow]}
        current={"source":"icheon","files":[oldfile,addedfile1,addedfile2],"rows":[oldrow,newrow]}
        d=assess_incremental("icheon",current,{"posts":[post([OLD,NEW1,NEW2])]},
                             old,{"posts":[post([OLD])]})
        self.assertEqual(d["status"],"HOLD")
        self.assertIn("official_file_without_transaction_rows",d["failures"])
        audit=diagnostic(old,current,{"posts":[post([OLD,NEW1,NEW2])]},d)
        self.assertEqual(len(audit["unlinked_new_files"]),1)
        self.assertEqual(audit["unlinked_new_files"][0]["url"],NEW2)
        self.assertEqual(audit["new_rows"],1)
        self.assertEqual(audit["lost_prior_rows"],0)

if __name__=="__main__":unittest.main()
