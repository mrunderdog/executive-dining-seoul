#!/usr/bin/env python3
"""Bupyeong P1 source-specific guarded release audit: strict QA and immutable history."""
import json, subprocess, sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"pipeline"))
from guard_full_council import check_integrity
from qa_council_publication import assess_incremental
from capital_backfill import canonical_attachment_url
from p2_release_audit import entity_snapshot

SOURCE="bupyeong"

def git_json(path):
    cp=subprocess.run(["git","show",f"HEAD:{path}"],cwd=ROOT,capture_output=True,text=True)
    return json.loads(cp.stdout) if cp.returncode==0 else {}

def main():
    before=git_json(f"data/raw/{SOURCE}_expense.json")
    prior_discovery=git_json(f"reports/capital-backfill-discovery-{SOURCE}.json")
    after=json.loads((ROOT/f"data/raw/{SOURCE}_expense.json").read_text(encoding="utf-8"))
    discovery=json.loads((ROOT/f"reports/capital-backfill-discovery-{SOURCE}.json").read_text(encoding="utf-8"))
    integrity=check_integrity(SOURCE,after,before)
    qa=assess_incremental(SOURCE,after,discovery,before,prior_discovery)
    old_by={r["row_id"]:r for r in before["rows"]}
    new=[r for r in after["rows"] if r["row_id"] not in old_by]
    reused=after.get("historical_duplicate_rows_verified",0)
    previously_authorized={canonical_attachment_url(f.get("url")) for f in before["files"]}
    new_files=[f for f in after["files"] if canonical_attachment_url(f.get("url")) not in previously_authorized]
    errors=[]
    if integrity["status"]!="PASS":errors.append("historical_integrity_failed")
    if qa["status"]!="PUBLISH_READY":errors.append("strict_qa_failed")
    if reused!=959:errors.append(f"expected 959 documented recycled 2025 rows, got {reused}")
    if len(new)!=92:errors.append(f"expected 92 real 2026 rows, got {len(new)}")
    if len(new_files)!=1:errors.append(f"expected 1 new official 2026 workbook, got {len(new_files)}")
    for r in new:
        if not str(r.get("used_date","")).startswith("2026-09-"):
            errors.append(f"row outside confirmed 2026-09 official period: {r['row_id']}")
        if canonical_attachment_url(r.get("source_attachment_url")) not in {canonical_attachment_url(f.get("url")) for f in new_files}:
            errors.append(f"new transaction provenance unknown: {r['row_id']}")
    seen_by_key=Counter((r.get("used_date"),r.get("merchant"),r.get("amount"),r.get("role"),r.get("source_sheet"),r.get("source_row")) for r in before["rows"])
    if any(seen_by_key[(r.get("used_date"),r.get("merchant"),r.get("amount"),r.get("role"),r.get("source_sheet"),r.get("source_row"))] for r in new):
        errors.append("new 2026 transaction duplicates an old event")
    report={"source":SOURCE,"status":"PASS" if not errors else "FAIL",
            "baseline_rows":len(before["rows"]),"total_rows":len(after["rows"]),"new_rows":len(new),
            "reused_source_rows_not_duplicated":reused,"new_official_files":len(new_files),
            "historical_integrity":integrity,"strict_qa":qa,
            "new_year_counts":dict(Counter(str(r.get("used_date"))[:4] for r in new)),
            "new_file_url":[f.get("url") for f in new_files],
            "errors":errors}
    path=ROOT/"reports/p1-bupyeong-strict-release-audit.json"
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("historical_integrity","strict_qa")},ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)

if __name__=="__main__":main()
