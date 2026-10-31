#!/usr/bin/env python3
"""P0 full-reconciliation safety: defend historical official rows/files.

Full mode may rediscover all official posts, but only *new* attachments may
introduce transactions. Historical records/files are immutable until a
separately reviewed migration. This guard does not weaken strict publication QA.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from capital_backfill import canonical_attachment_url

ROOT = Path(__file__).resolve().parents[1]


def baseline_json(ref: str, path: str) -> dict | None:
    p = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT,
                       text=True, capture_output=True)
    if p.returncode:
        return None
    return json.loads(p.stdout)


def file_map(files: list) -> tuple[dict, list]:
    result = {}
    problems = []
    for f in files:
        url = canonical_attachment_url(f.get("url"))
        if not url:
            problems.append("missing_file_url")
        elif url in result:
            problems.append(f"duplicate_file_url:{url}")
        else:
            result[url] = f
    return result, problems


def transaction_map(rows: list) -> tuple[dict, list]:
    result = {}
    problems = []
    for r in rows:
        rid = r.get("row_id")
        if not isinstance(rid, str) or not rid.strip():
            problems.append("missing_row_id")
        elif rid in result:
            problems.append(f"duplicate_row_id:{rid}")
        else:
            result[rid] = r
    return result, problems


def check_discovery(source: str, discovered: dict, baseline: dict | None) -> dict:
    problems = []
    posts = [p for p in discovered.get("posts", []) if p.get("source") == source]
    attachments = [a for p in posts for a in (p.get("attachments") or [])
                   if canonical_attachment_url(a.get("url"))]
    errors = [{"post_url": p.get("post_url"),"error":str(p.get("error"))}
              for p in posts if p.get("error")]
    if not posts:
        problems.append("no_official_posts_discovered")
    if not attachments:
        problems.append("no_official_attachment_urls_discovered")
    if errors:
        problems.append("incomplete_official_discovery")
    # Bupyeong publishes official monthly XLSX files under opaque numeric
    # /kr/news/bbs_process download IDs. A partial board/pagination response
    # can still show valid attachments while silently losing older, already
    # verified files. In a full refresh, require every previously published
    # in-window attachment to remain discoverable. Do not infer identities
    # from filenames or silently erase any historic transactions.
    missing_verified = []
    if source == "bupyeong" and baseline and discovered.get("since") and discovered.get("until"):
        from capital_backfill import period_overlaps
        def month_pair(value):
            year, month = str(value).split("-", 1)
            return int(year), int(month)
        try:
            since = month_pair(discovered["since"])
            until = month_pair(discovered["until"])
        except (TypeError, ValueError, AttributeError):
            problems.append("invalid_discovery_window")
        else:
            expected = set()
            for row in baseline.get("rows") or []:
                period = row.get("source_period")
                if not isinstance(period, (list, tuple)) or len(period) != 3:
                    continue
                if not period_overlaps(tuple(period), since, until):
                    continue
                url = canonical_attachment_url(row.get("source_attachment_url"))
                if url:
                    expected.add(url)
            found = {canonical_attachment_url(a.get("url")) for a in attachments}
            missing_verified = sorted(expected - found)
            if missing_verified:
                problems.append("previously_verified_official_attachments_missing")
    return {"source":source,"phase":"discovery",
            "status":"PASS" if not problems else "HOLD",
            "post_count":len(posts),"attachment_count":len(attachments),
            "baseline_rows":len((baseline or {}).get("rows") or []),
            "baseline_files":len((baseline or {}).get("files") or []),
            "discovery_errors":errors[:8],
            "missing_verified_attachment_count":len(missing_verified),
            "missing_verified_attachment_examples":missing_verified[:5],
            "failures":problems}


def check_integrity(source: str, current: dict, baseline: dict | None) -> dict:
    problems = []
    old = baseline or {}
    if current.get("source") != source:
        problems.append("source_mismatch")
    if baseline and baseline.get("source") != source:
        problems.append("baseline_source_mismatch")
    former, old_bad = transaction_map(old.get("rows") or [])
    fresh, new_bad = transaction_map(current.get("rows") or [])
    oldfiles, bad_oldfiles = file_map(old.get("files") or [])
    newfiles, bad_newfiles = file_map(current.get("files") or [])
    problems.extend(old_bad+new_bad+bad_oldfiles+bad_newfiles)
    lost_rows=sorted(set(former)-set(fresh))
    changed_rows=sorted(i for i in set(former)&set(fresh) if former[i]!=fresh[i])
    lost_files=sorted(set(oldfiles)-set(newfiles))
    changed_files=sorted(u for u in set(oldfiles)&set(newfiles) if oldfiles[u]!=newfiles[u])
    if lost_rows:problems.append("historical_rows_removed")
    if changed_rows:problems.append("historical_rows_modified")
    if lost_files:problems.append("historical_files_removed")
    if changed_files:problems.append("historical_file_metadata_modified")
    # A first publication without a valid source dataset cannot masquerade as success.
    if not fresh or not newfiles:problems.append("missing_ingested_official_rows_or_files")
    return {
        "source":source,"phase":"integrity",
        "status":"PASS" if not problems else "HOLD",
        "old_rows":len(former),"current_rows":len(fresh),
        "new_rows":len(set(fresh)-set(former)),
        "lost_row_count":len(lost_rows),"changed_row_count":len(changed_rows),
        "old_files":len(oldfiles),"current_files":len(newfiles),
        "new_files":len(set(newfiles)-set(oldfiles)),
        "lost_file_count":len(lost_files),"changed_file_count":len(changed_files),
        "examples":{"lost_rows":lost_rows[:5],"changed_rows":changed_rows[:5],
                    "lost_files":lost_files[:3],"changed_files":changed_files[:3]},
        "failures":sorted(set(problems))
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True)
    ap.add_argument("--phase",required=True,choices=["discovery","integrity"])
    ap.add_argument("--baseline-ref",default="HEAD")
    args=ap.parse_args()
    source=args.source
    baseline=baseline_json(args.baseline_ref,f"data/raw/{source}_expense.json")
    if args.phase=="discovery":
        p=ROOT/f"reports/capital-backfill-discovery-{source}.json"
        d=json.loads(p.read_text(encoding="utf-8"))
        verdict=check_discovery(source,d,baseline)
    else:
        p=ROOT/f"data/raw/{source}_expense.json"
        d=json.loads(p.read_text(encoding="utf-8"))
        verdict=check_integrity(source,d,baseline)
    print(json.dumps(verdict,ensure_ascii=False,indent=2),flush=True)
    if verdict["status"]!="PASS":
        raise SystemExit(2)


if __name__=="__main__":
    main()
