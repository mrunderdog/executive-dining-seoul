"""P0 immutable-baseline full-refresh safety regression fixtures."""
from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from guard_full_council import check_discovery, check_integrity
from ingest_council_expense import main as ingest_main

URL = "https://council.example.org/expense.pdf"
POST = "https://council.example.org/post/123"
OLD_ROW={"row_id":"old-1","source_key":"bupyeong","source_post_url":POST,
         "source_attachment_url":URL,"used_date":"2026-01-05","amount":15000,"merchant":"기존식당",
         "source_period":[2026,1,None],"date_quality":"in_period"}
OLD_FILE={"url":URL,"bytes":500,"sha256":"a"*64,"sheets":[]}
BASE={"source":"bupyeong","rows":[OLD_ROW],"files":[OLD_FILE]}

class FullReconciliationSafety(unittest.TestCase):
    def test_bupyeong_missing_all_attachment_urls_is_hold(self):
        d={"posts":[{"source":"bupyeong","post_url":POST,"attachments":[]} for _ in range(22)]}
        result=check_discovery("bupyeong",d,BASE)
        self.assertEqual(result["status"],"HOLD")
        self.assertIn("no_official_attachment_urls_discovered",result["failures"])

    def test_partial_official_listing_or_detail_error_is_hold(self):
        d={"posts":[{"source":"bupyeong","post_url":POST,"attachments":[{"url":URL}]},
                    {"source":"bupyeong","post_url":POST+"2","attachments":[],
                     "error":"listing RemoteDisconnected"}]}
        result=check_discovery("bupyeong",d,BASE)
        self.assertEqual(result["status"],"HOLD")
        self.assertIn("incomplete_official_discovery",result["failures"])

    def test_yongin_missing_rows_rejected(self):
        d=deepcopy(BASE)
        d["rows"]=[]
        out=check_integrity("bupyeong",d,BASE)
        self.assertEqual(out["lost_row_count"],1)
        self.assertIn("historical_rows_removed",out["failures"])

    def test_guri_pocheon_same_id_modified_rejected(self):
        d=deepcopy(BASE)
        d["rows"][0]["source_period"]=[2026,9,None]
        out=check_integrity("bupyeong",d,BASE)
        self.assertEqual(out["changed_row_count"],1)
        self.assertIn("historical_rows_modified",out["failures"])

    def test_old_file_metadata_changed_is_rejected(self):
        d=deepcopy(BASE);d["files"][0]["sha256"]="b"*64
        out=check_integrity("bupyeong",d,BASE)
        self.assertIn("historical_file_metadata_modified",out["failures"])

    def test_valid_append_keeps_old_bytes(self):
        d=deepcopy(BASE)
        new=deepcopy(OLD_ROW)
        new.update(row_id="new-2",source_attachment_url="https://council.example.org/new.pdf")
        d["rows"].append(new)
        d["files"].append({"url":new["source_attachment_url"],"bytes":600,"sha256":"b"*64})
        out=check_integrity("bupyeong",d,BASE)
        self.assertEqual(out["status"],"PASS",out)
        self.assertEqual(out["new_rows"],1)

    def test_duplicate_id_fails_and_never_seems_published(self):
        d=deepcopy(BASE);d["rows"].append(deepcopy(OLD_ROW))
        out=check_integrity("bupyeong",d,BASE)
        self.assertEqual(out["status"],"HOLD")
        self.assertIn("duplicate_row_id:old-1",out["failures"])

    def test_all_four_failed_baselines_preserve_separate_old_files(self):
        for source in ("bupyeong","yongin","guri","pocheon"):
            prior=deepcopy(BASE);prior["source"]=source
            current=deepcopy(prior)
            self.assertEqual(check_integrity(source,current,prior)["status"],"PASS")
            current["files"]=[]
            self.assertIn("historical_files_removed",
                          check_integrity(source,current,prior)["failures"])

if __name__=="__main__":
    unittest.main()
