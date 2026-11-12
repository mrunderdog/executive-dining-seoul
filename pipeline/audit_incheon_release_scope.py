#!/usr/bin/env python3
"""Reconcile official Incheon text-PDF downloads to independently counted originals.

Read-only and fail-closed. A CI-successful forensic collection is NOT a
publication approval; downloaded files can still fail SHA, row or page QA.
Scanned originals with inconsistent printed totals remain HOLD.
"""
from __future__ import annotations
import json
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/"pipeline/incheon_official_2026_08_09_text_evidence.json"
FORENSIC=ROOT/"reports/recovery/incheon-forensics/official_pdf_diagnostics.json"
OUTPUT=ROOT/"reports/recovery/incheon-source-reconciliation"

def analyze(forensic, evidence, scan):
    source={int(d["msg_seq"]):d for d in forensic.get("documents",[])}
    checks=[]
    missing=[]
    for original in evidence["files"]:
        seq=original["msg_seq"]
        observed=source.get(seq)
        issues=[]
        if not observed:
            issues.append("OFFICIAL_PDF_NOT_FETCHED")
        else:
            if observed.get("exceptions"):
                issues.append("OFFICIAL_DOWNLOAD_OR_TEXT_EXTRACTION_ERROR")
            if observed.get("sha256") != original["sha256"]:
                issues.append("OFFICIAL_SHA256_MISMATCH_OR_NOT_DOWNLOADED")
            if observed.get("pdf_page_count") != original["pages"]:
                issues.append("OFFICIAL_PAGE_COUNT_MISMATCH")
            if observed.get("parsed_count") != original["transactions"]:
                issues.append("OFFICIAL_ROW_COUNT_MISMATCH")
            total=sum(int(row.get("amount") or 0) for row in observed.get("transactions",[]))
            if total != original["amount_total_krw"]:
                issues.append("OFFICIAL_AMOUNT_SUM_MISMATCH")
            if any(p.get("current_parser",{}).get("status") not in
                   {"OK","DUPLICATE_OFFICIAL_PAGE_NO_NEW_ROWS"}
                   for p in observed.get("pages",[])):
                issues.append("OFFICIAL_PAGE_PARSE_HOLD")
            if seq==1330:
                pages=observed.get("pages",[])
                by_name={p.get("sheet"):p for p in pages}
                if (by_name.get("pdf-page-1",{}).get("current_parser",{}).get("status")
                    !="DUPLICATE_OFFICIAL_PAGE_NO_NEW_ROWS"
                    or by_name.get("pdf-page-2",{}).get("normalized_count")!=13):
                    issues.append("INDUSTRY_DUPLICATE_PAGE_UNVERIFIED")
            if seq==1320:
                pages=observed.get("pages",[])
                if ([p.get("normalized_count") for p in pages] != [15,5]
                    or not any(r.get("date")=="2026-08-31"
                               and r.get("amount")==25500
                               and r.get("merchant")=="본죽&비빔밥 인천서해구청점"
                               for r in observed.get("transactions",[]))):
                    issues.append("AUGUST_31_OR_HEADERLESS_PAGE_UNVERIFIED")
        result={"msg_seq":seq,"period":original["period"],
                "expected_count":original["transactions"],
                "expected_amount_krw":original["amount_total_krw"],
                "observed_rows":observed.get("parsed_count",0) if observed else 0,
                "observed_amount_krw":sum(int(r.get("amount") or 0)
                                         for r in observed.get("transactions",[])) if observed else 0,
                "status":"PASS" if not issues else "HOLD",
                "issues":issues}
        checks.append(result)
        if issues:missing.append(seq)
    scans={int(d["msg_seq"]):d for d in scan.get("documents",[])}
    scan_hold=(
        scans.get(1321,{}).get("printed_minus_rows_krw") != 438200 or
        scans.get(1321,{}).get("source_mismatch_status")
          != "HOLD_PRINTED_TOTAL_DIFFERS_FROM_ROW_SUM" or
        scans.get(1329,{}).get("printed_minus_rows_krw") != 0
    )
    if scan_hold:
        missing.append("SCANNED_SOURCE_EVIDENCE_INVALID")
    all_text=all(x["status"]=="PASS" for x in checks)
    return {
        "source":"incheon_council",
        "window":"2026-08..2026-09",
        "status":"TEXT_PDFS_VERIFIED_SCANS_HOLD" if all_text and not scan_hold
                 else "TEXT_PDFS_INCOMPLETE",
        "text_documents_expected":len(checks),
        "text_documents_verified":sum(x["status"]=="PASS" for x in checks),
        "text_rows_expected":sum(x["expected_count"] for x in checks),
        "text_rows_verified":sum(x["observed_rows"] for x in checks if x["status"]=="PASS"),
        "text_amount_expected_krw":sum(x["expected_amount_krw"] for x in checks),
        "text_amount_verified_krw":sum(x["observed_amount_krw"] for x in checks if x["status"]=="PASS"),
        "scanned_august_discrepancy_krw":scans.get(1321,{}).get("printed_minus_rows_krw"),
        "source_exceptions":missing,
        "files":checks,
        "strict_qa":"NOT_RELEASE_READY",
        "baseline_preserved":True,
        "publish":False,
    }


def main():
    forensic=json.loads(FORENSIC.read_text(encoding="utf-8"))
    evidence=json.loads(EVIDENCE.read_text(encoding="utf-8"))
    scan=json.loads((ROOT/"pipeline/incheon_scan_original_evidence.json").read_text(encoding="utf-8"))
    baseline_path=ROOT/"data/raw/incheon_council_expense.json"
    before_bytes=baseline_path.read_bytes()
    baseline=json.loads(before_bytes)
    result=analyze(forensic,evidence,scan)
    result["baseline_rows"]=len(baseline.get("rows",[]))
    result["baseline_files"]=len(baseline.get("files",[]))
    result["baseline_sha256"]=hashlib.sha256(before_bytes).hexdigest()
    result["baseline_preserved"]=(len(baseline.get("rows",[]))==194
                                   and len(baseline.get("files",[]))==10
                                   and baseline_path.read_bytes()==before_bytes)
    if not result["baseline_preserved"]:
        result["status"]="HOLD_BASELINE_CHANGED"
        result["source_exceptions"].append("baseline_194_rows_10_files_changed")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/"audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "status":result["status"],"verified_files":result["text_documents_verified"],
        "expected_files":result["text_documents_expected"],
        "verified_rows":result["text_rows_verified"],
        "expected_rows":result["text_rows_expected"],
        "failures":result["source_exceptions"],"publish":False
    },ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
