#!/usr/bin/env python3
"""Re-validate Police Agency PDFs from a previous verified Chromium capture.

Do not preserve a file just because a ZIP contains a .pdf extension: require
manifest URL, exact PDF sha256, official host, and reconciled PDF user/amount table.
The output is transaction staging, never a restaurant map publication feed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from police_browser_probe import police_url
from police_expense_pdf import parse_pdf

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/raw/police_expense_staging.json"

def replay(directory:Path, capture_run_id:int) -> dict:
    report=json.loads((directory/"reports/police-browser-attachment-probe.json").read_text(encoding="utf-8"))
    if report.get("publication_enabled") is not False:
        raise ValueError("browser capture must not authorize publication")
    rows={}
    evidence=[]
    for item in report.get("records") or []:
        detail_url=item.get("original_url") or ""
        role=item.get("role") or ""
        if not police_url(detail_url):
            continue
        for attempt in item.get("attempts") or []:
            for d in attempt.get("downloads") or []:
                if d.get("format")!="PDF" or not police_url(d.get("source_url") or ""):
                    continue
                sha=d.get("sha256") or ""
                if len(sha)!=64 or not all(c in "0123456789abcdef" for c in sha):
                    continue
                pdf=directory/"reports/police-browser-pdfs"/(sha[:16]+".pdf")
                if not pdf.exists():
                    continue
                data=pdf.read_bytes()
                if hashlib.sha256(data).hexdigest()!=sha:
                    raise ValueError("Official capture blob SHA mismatch: "+sha[:16])
                parsed,summary=parse_pdf(data,role,d["source_url"])
                for row in parsed:
                    row["source_detail_url"]=detail_url
                    rows[row["row_id"]]=row
                evidence.append({
                    "role":role,"source_url":d["source_url"],"detail_url":detail_url,
                    "sha256":sha,"bytes":len(data),
                    "rows":summary["records"],"total_won":summary["amount_total"],
                })
    return {"publication_enabled":False,"source":"official-police-chromium-capture",
            "capture_run_id":capture_run_id,"transactions":sorted(rows.values(),key=lambda x:(x["used_date"],x["row_id"])),
            "transactions_count":len(rows),"evidence":evidence,
            "caution":"PDF user column identifies senior expense user. It does not prove presence at a restaurant."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--directory",type=Path,required=True)
    p.add_argument("--capture-run-id",type=int,required=True)
    args=p.parse_args()
    doc=replay(args.directory,args.capture_run_id)
    if not doc["transactions"]:
        raise SystemExit("No checksum-verified official PDF transactions; nothing persisted")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"transactions":doc["transactions_count"],
           "official_pdfs":len(doc["evidence"]),
           "totals_won":sum(x["amount"] for x in doc["transactions"]),
           "publication_enabled":False},ensure_ascii=False))

if __name__=="__main__":main()
