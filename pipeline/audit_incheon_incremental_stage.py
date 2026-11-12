#!/usr/bin/env python3
"""Append-only 71-row staging trial: never write original 194-row source.

Explicitly reports existing official file metadata deficiencies and scan
exceptions. This script must NEVER issue a public recommendation approval.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

from capital_backfill import canonical_attachment_url
from guard_full_council import check_integrity
from qa_council_publication import assess_incremental

ROOT=Path(__file__).resolve().parents[1]
STAGED=ROOT/"reports/recovery/incheon-forensics/official_pdf_diagnostics.json"
OUTPUT=ROOT/"reports/recovery/incheon-incremental-qa"

def analyze(base, discovery, forensic):
    source="incheon_council"
    approved={1320,1322,1323,1326,1327,1330}
    docs={d["msg_seq"]:d for d in forensic.get("documents",[])}
    posts={}
    for p in discovery.get("posts",[]):
        for att in p.get("attachments",[]):
            url=canonical_attachment_url(att.get("url"))
            if url: posts[url]=p.get("post_url")
    original_ids={r["row_id"] for r in base["rows"]}
    evidence_rows=[]
    failures=[]
    for seq in sorted(approved):
        doc=docs.get(seq)
        if not doc or doc.get("exceptions") or len(doc.get("staged_full_rows",[]))==0:
            failures.append(f"official_{seq}_unavailable")
            continue
        url=canonical_attachment_url(doc["url"])
        exact_post=posts.get(url)
        if not exact_post:
            failures.append(f"official_{seq}_not_in_discovery")
            continue
        for row in doc["staged_full_rows"]:
            rec=dict(row)
            rec["source_post_url"]=exact_post
            rec["date_quality"]="source_verified_unranked" # simulation only
            rec["recommendation_status"]="HOLD_ORIGINAL_QA_AND_SCANS"
            if rec["row_id"] in original_ids:
                failures.append(f"existing_source_row_conflict_{seq}")
            evidence_rows.append(rec)
    ids=[r.get("row_id") for r in evidence_rows]
    if len(ids)!=len(set(ids)):
        failures.append("recovered_duplicate_transaction_id")
    proposed={**base, "rows":[*base.get("rows",[]),*evidence_rows]}
    integrity=check_integrity(source,proposed,base)
    qa=assess_incremental(source,proposed,discovery,base,discovery)
    if integrity["status"]!="PASS":
        failures+=integrity["failures"]
    if qa["status"]!="PUBLISH_READY":
        failures+=qa["failures"]
    if len(evidence_rows)!=71:
        failures.append("71_source_rows_not_complete")
    # Even if a subset of legacy files can be verified, the scanned
    # official 2026-08 ledger still has an unresolved 438,200 KRW mismatch.
    failures.append("official_2026_08_scanned_grand_total_438200_mismatch")
    return {
        "status":"HOLD",
        "baseline_rows":len(base.get("rows",[])),
        "baseline_files":len(base.get("files",[])),
        "recovered_rows":len(evidence_rows),
        "staged_total_rows":len(proposed["rows"]),
        "staged_total_files":len(proposed.get("files",[])),
        "integrity":integrity,
        "strict_qa_subset":qa,
        "release_criteria_satisfied":False,
        "site_rankings_changed":False,
        "publish":False,
        "failures":sorted(set(failures)),
    }


def main():
    original_path=ROOT/"data/raw/incheon_council_expense.json"
    old_bytes=original_path.read_bytes()
    base=json.loads(old_bytes)
    discovery=json.loads((ROOT/"reports/capital-backfill-discovery-incheon_council.json").read_text(encoding="utf-8"))
    source=json.loads(STAGED.read_text(encoding="utf-8"))
    audit=analyze(base,discovery,source)
    audit["baseline_sha256"]=hashlib.sha256(old_bytes).hexdigest()
    audit["baseline_byte_identical"]=original_path.read_bytes()==old_bytes
    if not audit["baseline_byte_identical"] or len(base["rows"])!=194 or len(base["files"])!=10:
        raise SystemExit("STOP: original 194/10 financial record changed")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/"audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "status":audit["status"],
        "old_rows":audit["baseline_rows"],
        "staged_rows":audit["staged_total_rows"],
        "new_rows":audit["recovered_rows"],
        "integrity":audit["integrity"]["status"],
        "source_qa":audit["strict_qa_subset"]["status"],
        "failures":audit["failures"],
        "publish":False,
    },ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
