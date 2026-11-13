#!/usr/bin/env python3
"""Read-only P1 partial source ledger review, never commit generated candidates.

Requires all official parsed rows to be accounted for in one of two groups:
verified in-period expense rows or an immutable SHA/file/sheet/row-specific
exception. Source original exceptions are NEVER silently dropped or imputed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from audit_ansan_hwaseong_full_reconcile import failures_for
from build_source_candidates import build_candidates
from capital_backfill import canonical_attachment_url
from guard_full_council import check_discovery,check_integrity
from qa_council_publication import assess_incremental

ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/"pipeline/p1_ansan_hwaseong_original_exceptions.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def git_json(rel):
    v=subprocess.run(["git","show",f"HEAD:{rel}"],cwd=ROOT,capture_output=True,text=True)
    if v.returncode:
        raise ValueError("missing committed source baseline: "+rel)
    return json.loads(v.stdout)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def check(source):
    plan=next((p for p in load(POLICY)["sources"] if p["source"]==source),None)
    if plan is None:
        raise ValueError("no source policy")
    old=git_json(f"data/raw/{source}_expense.json")
    old_discovery=git_json(f"reports/capital-backfill-discovery-{source}.json")
    file_path=ROOT/f"data/raw/{source}_expense.json"
    discovery_path=ROOT/f"reports/capital-backfill-discovery-{source}.json"
    staged_bytes=file_path.read_bytes()
    staged=json.loads(staged_bytes)
    discovery=load(discovery_path)
    audit=load(ROOT/f"reports/p1-ansan-hwaseong-qa/{source}.json")
    if (audit.get("status")!="HOLD" or audit.get("integrity",{}).get("status")!="PASS"
        or audit.get("discovery_guard",{}).get("status")!="PASS"):
        raise ValueError("full-source original audit not ready for exception review")
    if (len(old.get("rows",[]))!=plan["old_rows"]
        or len(old.get("files",[]))!=plan["old_files"]
        or len(staged.get("rows",[]))!=plan["stage_rows"]
        or len(staged.get("files",[]))!=plan["stage_files"]
        or audit.get("new_rows")!=plan["new_parsed"]
        or audit.get("new_files")!=plan["stage_files"]-plan["old_files"]):
        raise ValueError("current original official inventory diverges from audited policy")
    if (staged["rows"][:len(old["rows"])]!=old["rows"]
        or staged["files"][:len(old["files"])]!=old["files"]
        or staged.get("errors")!=old.get("errors")):
        raise ValueError("historical ledger changed in full refresh")
    old_ids={r["row_id"] for r in old["rows"]}
    fresh=[r for r in staged["rows"] if r["row_id"] not in old_ids]
    if len(fresh)!=plan["new_parsed"] or len({r["row_id"] for r in fresh})!=len(fresh):
        raise ValueError("new transactions incomplete or duplicate")
    new_file_info={canonical_attachment_url(f.get("url")):f
                   for f in staged["files"][len(old["files"]):]}
    if len(new_file_info)!=plan["stage_files"]-plan["old_files"]:
        raise ValueError("missing or duplicate new official attachment")
    if len(audit.get("new_file_evidence",[]))!=len(new_file_info):
        raise ValueError("unaccounted source files in original audit")
    official_evidence={canonical_attachment_url(x["url"]):x
                       for x in audit["new_file_evidence"]}
    if set(official_evidence)!=set(new_file_info):
        raise ValueError("audited and staged official files differ")
    for url,item in new_file_info.items():
        audit_file=official_evidence[url]
        if (item.get("sha256")!=audit_file.get("sha256")
            or item.get("bytes")!=audit_file.get("bytes")
            or not item.get("sha256") or len(item["sha256"])!=64):
            raise ValueError("SHA/bytes mismatch for "+url)
    except_policy={x["row_id"]:x for x in plan["exceptions"]}
    if len(except_policy)!=plan["invalid_count"]:
        raise ValueError("exception whitelist has duplicate or wrong count")
    observed_bad={r["row_id"]:r for r in fresh if failures_for(r)}
    if set(observed_bad)!=set(except_policy):
        raise ValueError("new official exception changed: "+str({
            "unexpected":sorted(set(observed_bad)-set(except_policy)),
            "missing":sorted(set(except_policy)-set(observed_bad)),
        }))
    by_audit_bad={x["row_id"]:x for f in audit["new_file_evidence"]
                  for x in f.get("examples",[])}
    if set(by_audit_bad)!=set(except_policy):
        raise ValueError("original file audit bad row evidence incomplete")
    original_cells=audit.get("original_source_cells") or []
    unresolved=[]
    for rid,pin in except_policy.items():
        row=observed_bad[rid]
        raw_url=canonical_attachment_url(row["source_attachment_url"])
        f=new_file_info.get(raw_url)
        if (not f or f.get("sha256")!=pin["file_sha256"]
            or row.get("source_sheet")!=pin["sheet"]
            or row.get("source_row")!=pin["source_row"]
            or row.get("used_date")!=pin["printed_date"]
            or row.get("amount")!=pin["amount"]
            or row.get("merchant")!=pin["merchant"]
            or failures_for(row)!=[pin["validation_error"]]
            or by_audit_bad[rid].get("errors")!=[pin["validation_error"]]):
            raise ValueError("original row/amount/SHA changed for: "+rid)
        cell_evidence=[c for c in original_cells if (
            c.get("file_sha256")==pin["file_sha256"] and
            c.get("sheet")==pin["sheet"] and
            c.get("sheet_row")==pin["source_row"] and
            c.get("parsed_date")==pin["printed_date"] and
            c.get("parsed_merchant")==pin["merchant"] and
            c.get("parsed_amount")==pin["amount"] and
            isinstance(c.get("exact_source_cells"),list))]
        if len(cell_evidence)!=1:
            raise ValueError("missing independent original XLSX cell read for: "+rid)
        unresolved.append({
            **copy.deepcopy(pin),
            "official_attachment_url":row["source_attachment_url"],
            "official_post_url":row["source_post_url"],
            "source_period":row["source_period"],
            "exact_source_cells":cell_evidence[0]["exact_source_cells"],
            "status":"HOLD_ORIGINAL_UNRESOLVED",
            "included_in_verified_source_rows":False,
            "included_in_restaurant_rankings":False,
        })
    good=[copy.deepcopy(r) for r in fresh if r["row_id"] not in except_policy]
    if len(good)!=plan["expected_valid"] or len(good)+len(unresolved)!=len(fresh):
        raise ValueError("total original expenditure accounting incomplete")
    if any(failures_for(r) for r in good):
        raise ValueError("invalid rows still in accepted subset")
    # Each source file is present, including those with a separately
    # documented source anomaly. Zero-new-transaction files are not allowed.
    by_new_file=Counter(canonical_attachment_url(r["source_attachment_url"]) for r in fresh)
    by_good_file=Counter(canonical_attachment_url(r["source_attachment_url"]) for r in good)
    by_bad_file=Counter(canonical_attachment_url(r["official_attachment_url"]) for r in unresolved)
    for url,record in official_evidence.items():
        if (by_new_file[url]!=record["parsed_rows"]
            or by_good_file[url]+by_bad_file[url]!=by_new_file[url]
            or by_bad_file[url]!=record["bad_rows"]
            or by_good_file[url]==0):
            raise ValueError("original per-file rows not fully accounted for: "+url)
    proposed=copy.deepcopy(staged)
    for row in good:
        row["date_quality"]="source_verified_unranked"
        row["ranking_eligible"]=False
        row["recommendation_status"]="HOLD_PAYMENT_BRANCH_UNVERIFIED"
    proposed["rows"]=[*old["rows"],*good]
    if proposed["rows"][:len(old["rows"])]!=old["rows"]:
        raise ValueError("historical source records modified")
    proposed["row_count"]=len(proposed["rows"])
    proposed["new_files"]=len(new_file_info)
    proposed["refresh_mode"]="verified_partial_original_exception_accounting"
    proposed["source_recovery"]={
        "source_status":"PARTIAL_EXPENSE_SOURCE_ONLY_WITH_EXPLICIT_EXCEPTIONS",
        "official_source_completeness":"HOLD_UNRESOLVED_ORIGINAL_ROWS",
        "official_attachment_sha_audit":True,
        "original_rows_parsed":len(fresh),
        "new_source_verified_unranked":len(good),
        "new_verified_row_total_krw":sum(r["amount"] for r in good),
        "original_exceptions_count":len(unresolved),
        "original_exceptions_total_krw":sum(r["amount"] for r in observed_bad.values()),
        "unresolved_original_expense_rows":unresolved,
        "ranking_eligible":False,
        "whole_disclosure_reconciled":False,
    }
    integrity=check_integrity(source,proposed,old)
    qa=assess_incremental(source,proposed,discovery,old,old_discovery)
    disc=check_discovery(source,discovery,old)
    if integrity["status"]!="PASS" or qa["status"]!="PUBLISH_READY" or qa.get("verified_rows")!=len(good) or disc["status"]!="PASS":
        raise ValueError(f"source-only subset QA failed: {integrity} {qa} {disc}")
    # The source's pre-existing recommendation data MUST NOT be changed. All
    # new good rows are explicitly excluded from scoring; test the existing
    # source candidate algorithm with the exact baseline and proposed raw.
    saved=file_path.read_bytes()
    before_candidate_file=ROOT/f"reports/{source}-executive-candidates.json"
    before_bytes=before_candidate_file.read_bytes()
    try:
        file_path.write_text(json.dumps(old,ensure_ascii=False)+"\n",encoding="utf-8")
        before_rank=build_candidates(source)[1]
        file_path.write_text(json.dumps(proposed,ensure_ascii=False)+"\n",encoding="utf-8")
        after_rank=build_candidates(source)[1]
        if before_rank!=after_rank or before_candidate_file.read_bytes()!=before_bytes:
            raise ValueError("existing recommendation data changed")
    finally:
        file_path.write_bytes(saved)
    result={
        "source":source,"status":"PARTIAL_SOURCE_ONLY_REVIEWABLE",
        "publish":False,"approved_to_merge":False,
        "base_rows":len(old["rows"]),"base_files":len(old["files"]),
        "official_file_count":len(staged["files"]),
        "official_new_parsed_rows":len(fresh),
        "new_source_only_valid_rows":len(good),
        "excluded_source_anomalies":len(unresolved),
        "excluded_original_amount_krw":sum(r["amount"] for r in observed_bad.values()),
        "proposed_total_rows":len(proposed["rows"]),
        "strict_qa":qa["status"],
        "verified_rows":qa["verified_rows"],
        "integrity":integrity["status"],
        "discovery":disc["status"],
        "historical_rows_modified":0,
        "historical_files_modified":0,
        "ranking_changes":0,
        "baseline_source_sha256":sha(json.dumps(old,ensure_ascii=False,sort_keys=True).encode()),
        "source_candidate_sha256":sha(json.dumps(proposed,ensure_ascii=False,sort_keys=True).encode()),
        "official_file_sums_accounted_for":True,
        "full_source_complete":False,
    }
    folder=ROOT/"reports/p1-ansan-hwaseong-qa"
    (folder/f"{source}-source-only-candidate.json").write_text(
        json.dumps(proposed,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (folder/f"{source}-source-exceptions.json").write_text(
        json.dumps(unresolved,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (folder/f"{source}-subset-manifest.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SOURCE_SUBSET_REVIEW",json.dumps(result,ensure_ascii=False),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True,choices=["ansan","hwaseong"])
    options=parser.parse_args()
    check(options.source)


if __name__=="__main__":
    main()
