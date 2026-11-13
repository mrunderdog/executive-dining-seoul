#!/usr/bin/env python3
"""One-shot, SHA-and-row-count-gated Ansan source-only partial release.

Authenticated official source data comes solely from previously CI-audited
artifact. The three unresolved official expense rows stay in a conspicuous
exception ledger, never merged into merchant rankings. This program writes
only data/raw and discovery JSON in its transient PR branch.
"""
import copy
import hashlib
import json
import os
from collections import Counter
from datetime import date,datetime,timezone
from pathlib import Path

from build_source_candidates import build_candidates
from guard_full_council import check_integrity
from qa_council_publication import assess_incremental,period_bounds
from capital_backfill import canonical_attachment_url

ROOT=Path(__file__).resolve().parents[1]
PKG=Path(os.environ["RUNNER_TEMP"])/"ansan-source"/"recovery"/"ansan-source-only-review"
RAW=ROOT/"data/raw/ansan_expense.json"
DISC=ROOT/"reports/capital-backfill-discovery-ansan.json"
CAND=ROOT/"reports/ansan-executive-candidates.json"
EXPECTED_BAD={
    "23df3679b893ae2c101e":("f725087da2cf0faf0e441cea874e68cbb109ef15f17b0712b61e1dabd1a878f8",100000),
    "198c5aeadec480720c61":("fe291563e5d767510026f56838a27f1ffe118174c68fbfc5bf5179b24febda84",200500),
    "92d6fbb6c52941ece2b6":("fe291563e5d767510026f56838a27f1ffe118174c68fbfc5bf5179b24febda84",196700),
}

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def stop(msg):
    raise RuntimeError("STOP: "+msg)

def main():
    oldbytes=RAW.read_bytes()
    discoverybytes=DISC.read_bytes()
    candbytes=CAND.read_bytes()
    old=json.loads(oldbytes)
    olddisc=json.loads(discoverybytes)
    before=build_candidates("ansan")[1]
    proposed=read(PKG/"ansan_expense.json")
    posts=read(PKG/"capital-backfill-discovery-ansan.json")
    audit=read(PKG/"source-only-hold-manifest.json")
    if (len(old.get("rows",[]))!=658 or len(old.get("files",[]))!=2
        or len(proposed.get("rows",[]))!=2991
        or len(proposed.get("files",[]))!=8
        or old.get("source")!="ansan"
        or audit.get("status")!="SOURCE_ONLY_PARTIAL_REVIEWABLE"
        or audit.get("full_source_status")!="HOLD_3_ORIGINAL_EXPENSE_EXCEPTIONS"
        or audit.get("strict_qa",{}).get("status")!="PUBLISH_READY"
        or audit.get("strict_qa",{}).get("verified_rows")!=2333
        or audit.get("data_integrity",{}).get("status")!="PASS"
        or audit.get("old_rows")!=658 or audit.get("old_files")!=2
        or audit.get("new_verified_rows")!=2333
        or audit.get("existing_candidate_count")!=83
        or audit.get("new_recommendation_published")!=0
        or audit.get("publish") is not False
        or audit.get("approved_to_merge") is not False):
        stop("unrecognized audited source package")
    if proposed["rows"][:658]!=old["rows"] or proposed["files"][:2]!=old["files"]:
        stop("historic source rows/files not immutable")
    if olddisc["posts"]!=posts["posts"][:len(olddisc["posts"])] or len(posts["posts"])!=len(olddisc["posts"])+6:
        stop("official source discovery must be append-only by 6 posts")
    exceptions=proposed.get("source_recovery",{}).get("unresolved_original_expenses") or []
    if (len(exceptions)!=3 or
        {x["row_id"] for x in exceptions}!=set(EXPECTED_BAD) or
        sum(x["printed_amount_krw"] for x in exceptions)!=497200 or
        proposed["source_recovery"].get("full_official_document_reconciliation") is not False or
        proposed["source_recovery"].get("new_transaction_ranking_eligible") is not False):
        stop("missing or altered official 3-row HOLD")
    hashes={canonical_attachment_url(f["url"]):f.get("sha256") for f in proposed["files"]}
    for item in exceptions:
        expected_sha,amount=EXPECTED_BAD[item["row_id"]]
        if (item["sha256"]!=expected_sha or item["printed_amount_krw"]!=amount
            or hashes.get(canonical_attachment_url(item["official_attachment_url"]))!=expected_sha):
            stop("official original row SHA/amount changed")
    for row in proposed["rows"][658:]:
        bounds=period_bounds(row.get("source_period"))
        try:used=date.fromisoformat(row["used_date"])
        except (KeyError,TypeError,ValueError):stop("invalid official expense date")
        if (not bounds or not bounds[0]<=used<=bounds[1]
            or row.get("date_quality")!="source_verified_unranked"
            or row.get("ranking_eligible") is not False
            or row.get("source_key")!="ansan"
            or row.get("recommendation_status")!="HOLD_PAYMENT_BRANCH_IDENTITY_UNVERIFIED"
            or not isinstance(row.get("amount"),int) or row["amount"]<=0):
            stop("transaction source-only classification invalid")
    ids=[r.get("row_id") for r in proposed["rows"]]
    if len(ids)!=len(set(ids)):stop("duplicate financial transaction IDs")
    if audit.get("quarantine_amount_krw")!=497200:
        stop("unaccounted original exception financial amounts")
    proposed["source_recovery"]["status"]="INCOMPLETE_THREE_OFFICIAL_EXPENSES"
    proposed["source_recovery"]["release_mode"]="OFFICIAL_SOURCE_ONLY_PARTIAL_NOT_RANKED"
    proposed["source_recovery"]["audit_workflow_run"]=43400362218
    proposed["source_recovery"]["publish"]=True  # source ledger published, exceptions still held
    proposed["generated_at"]=datetime.now(timezone.utc).isoformat()
    sourceqa=assess_incremental("ansan",proposed,posts,old,olddisc)
    integrity=check_integrity("ansan",proposed,old)
    if sourceqa["status"]!="PUBLISH_READY" or sourceqa.get("verified_rows")!=2333 or integrity["status"]!="PASS":
        stop("strict source QA and original immutability failed "+str(sourceqa.get("failures")))
    RAW.write_text(json.dumps(proposed,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    DISC.write_text(json.dumps(posts,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    try:
        after=build_candidates("ansan")[1]
        if before!=after or CAND.read_bytes()!=candbytes or len(after)!=83:
            stop("public recommendation candidates or ranking changed")
    except Exception:
        RAW.write_bytes(oldbytes);DISC.write_bytes(discoverybytes)
        raise
    print(json.dumps({"mode":"SOURCE_ONLY_PARTIAL",
        "baseline":658,"new_verified":2333,"rows":2991,"source_files":8,
        "withheld_original_expenses":3,"withheld_krw":497200,
        "remaining_source_status":"INCOMPLETE_3_ORIGINAL_EXPENSES",
        "strict_qa":sourceqa["status"],"data_integrity":integrity["status"],
        "new_recommendation_records":0},ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
