#!/usr/bin/env python3
"""Non-publishing integrated Uiwang 2026-Q3 + October source QA gate.

Consumes SAME-workflow artifacts; does not download again or mutate raw data.
The 7-10 period is a bounded source audit, not authorization to publish.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from capital_backfill import canonical_attachment_url
from guard_full_council import check_integrity
from qa_council_publication import assess_incremental
from replay_failed_uiwang_pdfs import apply_dining_dispositions

ROOT=Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_integrated(baseline, discovery, q3_rows, october_rows, q3_audit,
                      october_audit, october_evidence, q3_policy, oct_policy):
    failures=[]
    if q3_audit.get("status")!="READY_FOR_REVIEW" or q3_audit.get("independent_official_evidence",{}).get("status")!="PASS":
        failures.append("q3_official_audit_not_ready")
    if october_audit.get("status")!="READY_FOR_CLASSIFICATION":
        failures.append("october_official_audit_not_ready")
    if october_audit.get("strict_qa",{}).get("status")!="PUBLISH_READY":
        failures.append("october_strict_qa_not_ready")
    if len(q3_rows)!=144 or len(october_rows)!=74:
        failures.append("expected_monthly_candidate_counts_mismatch")
    byid={}
    for row in [*(baseline.get("rows") or []),*q3_rows,*october_rows]:
        rid=row.get("row_id")
        if not rid or rid in byid:
            failures.append("duplicate_or_missing_integrated_row_id")
        else:
            byid[rid]=row
    q3_r=apply_dining_dispositions(q3_rows,q3_policy)
    oct_r=apply_dining_dispositions(october_rows,oct_policy)
    if q3_r["status"]!="PASS":
        failures+=["q3_recommendation_policy_hold"]+q3_r["failures"]
    if oct_r["status"]!="PASS":
        failures+=["october_recommendation_policy_hold"]+oct_r["failures"]
    october_files=[]
    for expected in october_evidence.get("items",[]):
        found=next((f for f in october_audit.get("file_results",[])
                    if canonical_attachment_url(f.get("url"))==canonical_attachment_url(expected["url"])),None)
        if not found or not found.get("sha256") or not found.get("bytes"):
            failures.append("missing_verified_october_file")
            continue
        october_files.append({
            "name":expected["name"],"title":"2026년 10월 업무추진비 사용내역 공개",
            "url":expected["url"],"sha256":found["sha256"],"bytes":found["bytes"],
            "sheets":[{"sheet":p["sheet"],"status":p["status"],
                       "parsed_rows":p.get("parsed_rows",0),
                       "unparsed_transaction_like_rows":p.get("unparsed_transaction_like_rows",0)}
                      for p in found.get("pages",[])]
        })
    post={"source":"uiwang","region":"경기","jurisdiction":"의왕시",
          "institution":"의왕시의회","title":"2026년 10월 업무추진비 사용내역 공개",
          "post_url":october_evidence["official_post"],"period":[2026,10,None],
          "attachments":[{"url":x["url"],"text":x["name"]} for x in october_evidence.get("items",[])]}
    new_discovery={**discovery,"posts":[*(discovery.get("posts") or []),post]}
    combined={
        **baseline,
        "rows":[*(baseline.get("rows") or []),*q3_rows,*october_rows],
        "files":[*(baseline.get("files") or []),*october_files]
    }
    integrity=check_integrity("uiwang",combined,baseline)
    qa=assess_incremental("uiwang",combined,new_discovery,baseline,discovery)
    if integrity["status"]!="PASS":
        failures+=["integrity_gate_failed"]+integrity["failures"]
    if qa["status"]!="PUBLISH_READY":
        failures+=["integrated_strict_qa_failed"]+qa["failures"]
    months={(row.get("source_period") or [None,None])[0:2][1]
            for row in q3_rows+october_rows}
    if months!={7,8,9,10}:
        failures.append("missing_month_coverage")
    target_recommendations=q3_r["remaining_candidates"]+oct_r["remaining_candidates"]
    result={
       "status":"READY_FOR_RELEASE_REVIEW" if not failures else "HOLD",
       "baseline_rows":len(baseline.get("rows") or []),
       "baseline_files":len(baseline.get("files") or []),
       "added_q3_rows":len(q3_rows),
       "added_october_rows":len(october_rows),
       "total_staged_rows":len(combined["rows"]),
       "total_staged_files":len(combined["files"]),
       "q3_recommendation_candidates":len(q3_r["remaining_candidates"]),
       "october_recommendation_candidates":len(oct_r["remaining_candidates"]),
       "total_new_recommendation_candidates":len(target_recommendations),
       "q3_disposition_status":q3_r["status"],
       "october_disposition_status":oct_r["status"],
       "strict_qa":qa,"integrity":integrity,
       "failures":sorted(set(failures)),
       "publish":False,
       "note":"Pre-release staging only. Requires human review of merchant names and production ranking behavior.",
    }
    return result, target_recommendations


def main():
    q3_dir=ROOT/"reports/recovery/uiwang-replay"
    oct_dir=ROOT/"reports/recovery/uiwang-october"
    baseline=load(ROOT/"data/raw/uiwang_expense.json")
    discovery=load(ROOT/"reports/capital-backfill-discovery-uiwang.json")
    result,recommended=verify_integrated(
        baseline,discovery,
        load(q3_dir/"candidate_rows.json"),load(oct_dir/"candidate_rows.json"),
        load(q3_dir/"audit.json"),load(oct_dir/"audit.json"),
        load(ROOT/"pipeline/uiwang_official_2026_10_evidence.json"),
        load(ROOT/"pipeline/uiwang_2026_q3_dining_dispositions.json"),
        load(ROOT/"pipeline/uiwang_2026_10_dining_dispositions.json"))
    output=ROOT/"reports/recovery/uiwang-integrated"
    output.mkdir(parents=True,exist_ok=True)
    (output/"audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (output/"recommendation_candidates.json").write_text(
        json.dumps(recommended,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in (
        "status","added_q3_rows","added_october_rows","total_staged_rows",
        "total_new_recommendation_candidates","failures","publish"
    )},ensure_ascii=False),flush=True)
    if result["status"]!="READY_FOR_RELEASE_REVIEW":
        raise SystemExit(2)


if __name__=="__main__":
    main()
