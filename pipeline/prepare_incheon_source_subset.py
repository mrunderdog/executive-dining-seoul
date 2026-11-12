#!/usr/bin/env python3
"""Create a review-only *source subset* package, without altering main.

The package is 194 immutable historical rows + 71 independently verified PDF
transactions. Two image-only PDFs are deliberately quarantined and NOT silently
counted as complete. Historical NO_HEADER file metadata stays byte-equivalent;
attested evidence is a *separate* approval artifact. Ranking files unchanged.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path

from audit_incheon_incremental_stage import ROOT, analyze
from audit_incheon_release_scope import analyze as reconcile
from capital_backfill import canonical_attachment_url
from guard_full_council import check_integrity
from incheon_reparse_attestation import attest_legacy_files, make_attested_qa_view
from qa_council_publication import assess_incremental

OUT=ROOT/"reports/recovery/incheon-source-subset"
EXPECTED={1320:20,1322:12,1323:2,1326:12,1327:12,1330:13}

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write(path,doc):
    path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def build(base,discovery,forensic,independent,scan):
    failures=[]
    report=reconcile(forensic,independent,scan)
    if report.get("status")!="TEXT_PDFS_VERIFIED_SCANS_HOLD":
        failures.append("independent_text_reconciliation_not_pass")
    docs={int(d["msg_seq"]):d for d in forensic.get("documents",[])}
    if set(EXPECTED)-set(docs): failures.append("six_expected_original_pdfs_missing")
    by_url={}
    for p in discovery.get("posts",[]):
        for a in p.get("attachments",[]):
            url=canonical_attachment_url(a.get("url"))
            if url:by_url[url]=p.get("post_url")
    package=copy.deepcopy(base)
    staged_discovery=copy.deepcopy(discovery)
    originals=copy.deepcopy(base)
    new=[]
    for seq,count in EXPECTED.items():
        doc=docs.get(seq)
        if not doc or doc.get("exceptions") or len(doc.get("staged_full_rows",[]))!=count:
            failures.append(f"official_{seq}_missing_or_unparsed")
            continue
        url=canonical_attachment_url(doc["url"])
        post=by_url.get(url)
        if seq==1330 and not post:
            post="https://www.icouncil.go.kr/main/bbs/bbsMsgDetail.do?bcd=infordisc&msg_seq=1330"
            staged_discovery["posts"].append({
                "source":"incheon_council","region":"인천",
                "jurisdiction":"인천광역시","institution":"인천광역시의회",
                "title":"2026년 9월 산업경제위원장 업무추진비 지출내역",
                "post_url":post,"period":[2026,9,None],
                "attachments":[{"url":doc["url"],"text":"2026년 9월 산업경제위원장 공식 PDF"}],
            })
            by_url[url]=post
            package["files"].append({
                "title":"2026년 9월 산업경제위원장 업무추진비 지출내역",
                "url":doc["url"],"name":"2026년 9월 산업경제위원장 업무추진비 지출내역.pdf",
                "sha256":doc["sha256"],"bytes":doc["bytes"],
                "sheets":[{**p["current_parser"],"sheet":p["sheet"]}
                          for p in doc["pages"]],
            })
        if not post:
            failures.append(f"official_{seq}_missing_discovery_post")
            continue
        for x in doc["staged_full_rows"]:
            rec=copy.deepcopy(x)
            rec["source_post_url"]=post
            rec["date_quality"]="source_verified_unranked"
            rec["recommendation_status"]="HOLD_ORIGINAL_QA_AND_SCAN_COVERAGE"
            new.append(rec)
    package["rows"].extend(new)
    if len(new)!=71 or len(package["rows"])!=265 or len(package["files"])!=11:
        failures.append("expected_194_plus_71_scope_incomplete")
    proof,attested=attest_legacy_files(originals,forensic,independent)
    if proof["status"]!="PASS":
        failures+=proof["failures"]
        qa={"status":"HOLD","failures":["attestation_unverified"]}
    else:
        view=make_attested_qa_view(package,attested,proof)
        qa=assess_incremental("incheon_council",view,staged_discovery,originals,discovery)
    integrity=check_integrity("incheon_council",package,originals)
    if integrity["status"]!="PASS": failures+=integrity["failures"]
    if qa["status"]!="PUBLISH_READY" or qa.get("verified_rows")!=71:
        failures+=qa.get("failures") or ["strict_qa_71_of_71_failed"]
    if package["rows"][:len(originals["rows"])]!=originals["rows"]:
        failures.append("immutable_original_rows_changed")
    if package["files"][:len(originals["files"])]!=originals["files"]:
        failures.append("immutable_original_files_changed")
    original_ids={r["row_id"] for r in originals["rows"]}
    if len({r.get("row_id") for r in new})!=len(new) or original_ids.intersection(
            {r.get("row_id") for r in new}):
        failures.append("new_transaction_duplicate_or_historic_collision")
    excluded=[
        {"msg_seq":1321,"period":"2026-08",
         "status":"QUARANTINE_PRINTED_TOTAL_DISCREPANCY",
         "difference_krw":438200,
         "decision":"not_in_subset_and_not_approved_as_complete"},
        {"msg_seq":1329,"period":"2026-09",
         "status":"QUARANTINE_MERCHANT_VERIFICATION",
         "difference_krw":0,
         "decision":"not_in_subset_and_not_approved_as_complete"}
    ]
    result={
        "status":"SOURCE_ONLY_SUBSET_REVIEWABLE" if not failures else "HOLD",
        "full_source_status":"HOLD_SCANNED_ORIGINALS",
        "financial_rows_before":len(originals.get("rows",[])),
        "financial_rows_after":len(package.get("rows",[])),
        "existing_files":len(originals.get("files",[])),
        "staged_files":len(package.get("files",[])),
        "new_verified_text_rows":len(new),
        "subset_new_recommendation_rows":0,
        "existing_recommendation_dataset_unchanged":True,
        "attestation":proof,
        "strict_qa_subset":qa,
        "integrity":integrity,
        "excluded_original_documents":excluded,
        "source_coverage":"PARTIAL_2026_08_09_OFFICIAL_SOURCE",
        "existing_metadata_preserved":True,
        "approved_to_merge":False,"publish":False,
        "failures":sorted(set(failures)),
    }
    return package,staged_discovery,result

def main():
    raw_path=ROOT/"data/raw/incheon_council_expense.json"
    discovery_path=ROOT/"reports/capital-backfill-discovery-incheon_council.json"
    candidates_path=ROOT/"reports/incheon_council-executive-candidates.json"
    originals=raw_path.read_bytes()
    cand_before=candidates_path.read_bytes()
    d=discovery_path.read_bytes()
    staged=read(ROOT/"reports/recovery/incheon-forensics/official_pdf_diagnostics.json")
    a=read(ROOT/"pipeline/incheon_official_2026_08_09_text_evidence.json")
    scans=read(ROOT/"pipeline/incheon_scan_original_evidence.json")
    package,new_discovery,result=build(json.loads(originals),json.loads(d),staged,a,scans)
    if (raw_path.read_bytes()!=originals or discovery_path.read_bytes()!=d
        or candidates_path.read_bytes()!=cand_before):
        raise SystemExit("STOP: original files were mutated")
    OUT.mkdir(parents=True,exist_ok=True)
    write(OUT/"incheon_council_expense.json",package)
    write(OUT/"capital-backfill-discovery-incheon_council.json",new_discovery)
    write(OUT/"reparse_attestation.json",result["attestation"])
    result["baseline_sha256"]=sha(originals)
    result["baseline_discovery_sha256"]=sha(d)
    result["unchanged_candidates_sha256"]=sha(cand_before)
    result["staged_sha256"]=sha((OUT/"incheon_council_expense.json").read_bytes())
    write(OUT/"manifest.json",result)
    print(json.dumps({"status":result["status"],
                      "full_source_status":result["full_source_status"],
                      "rows":result["financial_rows_after"],
                      "verified_new":result["new_verified_text_rows"],
                      "strict_qa":result["strict_qa_subset"]["status"],
                      "integrity":result["integrity"]["status"],
                      "scan_discrepancy":438200,"publish":False,
                      "failures":result["failures"]},
                     ensure_ascii=False),flush=True)
    if result["status"]!="SOURCE_ONLY_SUBSET_REVIEWABLE":
        raise SystemExit(2)

if __name__=="__main__":
    main()
