#!/usr/bin/env python3
"""Ansan source-only *partial* staging audit.

Read-only output from the existing full refresh sandbox (never git commit).
Preserves 658 old transactions and explicitly quarantines exactly three
official source anomalies instead of inventing a date or merchant.
"""
from __future__ import annotations
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

from audit_ansan_hwaseong_full_reconcile import failures_for, git_json
from capital_backfill import canonical_attachment_url
from guard_full_council import check_integrity
from qa_council_publication import assess_incremental

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/recovery/ansan-source-only-review"

EXCEPTIONS={
    "23df3679b893ae2c101e":{
      "status":"HOLD_NON_DINING_CASH_PAYMENT_NO_MERCHANT",
      "expected_reason":["merchant_invalid"],
      "sha256":"f725087da2cf0faf0e441cea874e68cbb109ef15f17b0712b61e1dabd1a878f8",
      "printed_amount_krw":100000,
      "printed_date":"2026-02-03",
      "source":"2026 Q1 기관운영 sheet row 10",
      "recommended_handling":"financial cash source exception only; not a restaurant or mapping candidate"
    },
    "198c5aeadec480720c61":{
      "status":"HOLD_WEEKLY_DATE_RANGE_NO_SINGLE_TRANSACTION_DATE",
      "expected_reason":["invalid_date"],
      "sha256":"fe291563e5d767510026f56838a27f1ffe118174c68fbfc5bf5179b24febda84",
      "printed_amount_krw":200500,
      "printed_date":"24.11.25.~11.29.",
      "source":"2024 Q4 의정운영공통경비 row 90",
      "recommended_handling":"retain exact weekly date range; do not fabricate or choose a single date"
    },
    "92d6fbb6c52941ece2b6":{
      "status":"HOLD_WEEKLY_DATE_RANGE_NO_SINGLE_TRANSACTION_DATE",
      "expected_reason":["invalid_date"],
      "sha256":"fe291563e5d767510026f56838a27f1ffe118174c68fbfc5bf5179b24febda84",
      "printed_amount_krw":196700,
      "printed_date":"24.12.2.~12.6.",
      "source":"2024 Q4 의정운영공통경비 row 98",
      "recommended_handling":"retain exact weekly date range; do not fabricate or choose a single date"
    },
}

def stage(baseline,discovery_baseline,candidate,discovery,initial_candidates):
    if len(baseline.get("rows",[]))!=658 or len(baseline.get("files",[]))!=2:
        raise ValueError("Unexpected historic 658/2 baseline")
    if len(candidate.get("rows",[]))!=2994 or len(candidate.get("files",[]))!=8:
        raise ValueError("Unexpected official source 2994/8 inventory")
    integrity_full=check_integrity("ansan",candidate,baseline)
    if integrity_full["status"]!="PASS":
        raise ValueError("Immutable historical rows/files were modified")
    # The refresh is allowed to re-order old rows/files. Build an append-only
    # package using the original prefix; never equate position with identity.
    old_by_id={r["row_id"]:r for r in baseline["rows"]}
    new_by_id={r["row_id"]:r for r in candidate["rows"]}
    if (any(new_by_id.get(key)!=row for key,row in old_by_id.items())
        or len(new_by_id)!=len(candidate["rows"])):
        raise ValueError("Historical transaction changed or duplicate ID")
    previous={canonical_attachment_url(f["url"]):f for f in baseline["files"]}
    discovered={canonical_attachment_url(f["url"]):f for f in candidate["files"]}
    if any(discovered.get(key)!=value for key,value in previous.items()):
        raise ValueError("Historic original attachment modified")
    old_ids={r["row_id"] for r in baseline["rows"]}
    new=[r for r in candidate["rows"] if r.get("row_id") not in old_ids]
    if len(new)!=2336:
        raise ValueError("Expected exactly 2336 newly parsed source records")
    bad={r["row_id"]:r for r in new if failures_for(r)}
    if set(bad)!=set(EXCEPTIONS):
        raise ValueError(f"Unexpected excluded official rows: {sorted(bad)}")
    official_files={canonical_attachment_url(f["url"]):f for f in candidate["files"]}
    held=[]
    for rid in sorted(bad):
        r=bad[rid];expected=EXCEPTIONS[rid]
        url=canonical_attachment_url(r.get("source_attachment_url"))
        original=official_files.get(url)
        if (original is None or original.get("sha256")!=expected["sha256"]
            or failures_for(r)!=expected["expected_reason"]
            or r.get("amount")!=expected["printed_amount_krw"]
            or r.get("used_date")!=expected["printed_date"]):
            raise ValueError(f"Official original exception evidence changed {rid}")
        held.append({**expected,"row_id":rid,"official_attachment_url":url,
                     "original_source_sheet":r.get("source_sheet"),
                     "original_source_row":r.get("source_row"),
                     "original_merchant":r.get("merchant")})
    eligible=[copy.deepcopy(r) for r in new if not failures_for(r)]
    if len(eligible)!=2333:
        raise ValueError("Ansan valid source subset count changed")
    for r in eligible:
        r["date_quality"]="source_verified_unranked"
        r["recommendation_status"]="HOLD_PAYMENT_BRANCH_IDENTITY_UNVERIFIED"
        r["ranking_eligible"]=False
    proposed=copy.deepcopy(candidate)
    proposed["rows"]=[*baseline["rows"],*eligible]
    proposed["files"]=[*baseline["files"],*[f for f in candidate["files"]
                           if canonical_attachment_url(f["url"]) not in previous]]
    proposed["row_count"]=len(proposed["rows"])
    q=copy.deepcopy(candidate.get("raw_quality") or {})
    q["rows"]=q["transaction_rows"]=len(proposed["rows"])
    proposed["raw_quality"]=q
    proposed["refresh_mode"]="partial_official_source_verified_not_ranking_eligible"
    proposed["source_recovery"]={
        "scope":"PARTIAL_2024Q4_2026Q1_OFFICIAL_SOURCE",
        "status":"INCOMPLETE_3_ORIGINAL_EXPENSE_EXCEPTIONS",
        "verified_new_rows":2333,
        "unresolved_original_expenses":held,
        "excluded_not_silent":True,
        "missing_expense_total_krw":sum(x["printed_amount_krw"] for x in held),
        "new_transaction_ranking_eligible":False,
        "full_official_document_reconciliation":False,
        "publish":False,
    }
    integrity=check_integrity("ansan",proposed,baseline)
    qa=assess_incremental("ansan",proposed,discovery,baseline,discovery_baseline)
    checks={
        "status":"SOURCE_ONLY_PARTIAL_REVIEWABLE" if
            integrity["status"]=="PASS" and qa["status"]=="PUBLISH_READY"
            and qa.get("verified_rows")==2333 else "HOLD",
        "full_source_status":"HOLD_3_ORIGINAL_EXPENSE_EXCEPTIONS",
        "old_rows":658,"old_files":2,
        "new_verified_rows":len(eligible),
        "new_official_files":len(candidate["files"])-2,
        "staged_total_rows":len(proposed["rows"]),
        "staged_total_files":len(proposed["files"]),
        "quarantined_unverified_expenses":held,
        "quarantine_amount_krw":sum(x["printed_amount_krw"] for x in held),
        "strict_qa":qa,"data_integrity":integrity,
        "new_recommendation_published":0,
        "existing_candidate_count":initial_candidates["candidate_count"],
        "review_only":True,"approved_to_merge":False,"publish":False,
    }
    if checks["status"]!="SOURCE_ONLY_PARTIAL_REVIEWABLE":
        raise ValueError("Ansan 2333-row source-only staging QA HOLD: "+json.dumps(checks,ensure_ascii=False)[:1700])
    return proposed,checks

def main():
    raw_path=ROOT/"data/raw/ansan_expense.json"
    discovery_path=ROOT/"reports/capital-backfill-discovery-ansan.json"
    orig=git_json("data/raw/ansan_expense.json")
    olddisc=git_json("reports/capital-backfill-discovery-ansan.json")
    current=json.loads(raw_path.read_text(encoding="utf-8"))
    disc=json.loads(discovery_path.read_text(encoding="utf-8"))
    current_candidates=json.loads((ROOT/"reports/ansan-executive-candidates.json").read_text(encoding="utf-8"))
    result,manifest=stage(orig,olddisc,current,disc,current_candidates)
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/"ansan_expense.json"
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"capital-backfill-discovery-ansan.json").write_text(
        json.dumps(disc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"source-only-hold-manifest.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    manifest["baseline_sha256"]=hashlib.sha256(json.dumps(orig,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    print(json.dumps({"source":"ansan","result":manifest["status"],
                      "staged_rows":manifest["staged_total_rows"],
                      "staged_files":manifest["staged_total_files"],
                      "verified_new_rows":manifest["new_verified_rows"],
                      "hold_originals":len(manifest["quarantined_unverified_expenses"]),
                      "quarantine_amount_krw":manifest["quarantine_amount_krw"],
                      "strict_qa":manifest["strict_qa"]["status"],
                      "integrity":manifest["data_integrity"]["status"],
                      "publish":False},ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
