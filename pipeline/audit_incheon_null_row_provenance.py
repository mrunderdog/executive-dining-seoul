#!/usr/bin/env python3
"""Read-only provenance comparator for unresolved Incheon Council null-amount row.

Compares previously observed unknown row ID with SHA-pinned official source
PDF #1320. Same date alone cannot prove identity: retain HOLD until the
actual failed candidate's source_attachment_url, source_sheet and source_row
are independently captured.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

MISSING_ROW_ID="e6256a2ab172f5fd2ac7"
PINNED_SHA="d85541d349a5f5e20fb4023be5c34093ad59a7e80483a3409af2c61143ef6dcb"
OFFICIAL_URL="https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&fileno=1&msg_seq=1320"

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--artifact-dir",type=Path,required=True)
    a.add_argument("--out",type=Path,required=True)
    args=a.parse_args()
    pdf=args.artifact_dir/"official-1320.pdf"
    receipt=args.artifact_dir/"evidence.json"
    if not pdf.exists() or not receipt.exists():
        raise SystemExit("HOLD: missing independent official source artifacts")
    d=json.loads(receipt.read_text(encoding="utf-8"))
    if d.get("status")!="CAPTURED_BASELINE_SHA_OK" or d.get("seq")!=1320 or d.get("official_file")!=OFFICIAL_URL:
        raise SystemExit("HOLD: bad source receipt")
    observed=hashlib.sha256(pdf.read_bytes()).hexdigest()
    if observed!=PINNED_SHA or d.get("observed_sha256")!=observed:
        raise SystemExit("HOLD: source PDF SHA mismatch")
    located=[]
    for section in d.get("sections",[]):
        for row in section.get("original_rows",[]):
            vals=row.get("cells",[])
            if any("2026-08-31" in str(x) for x in vals):
                located.append({"source_sheet":section.get("name"),"source_row":row.get("n"),"source_cells":vals})
    if len(located)!=1 or not any("25,500" in str(v) for v in located[0]["source_cells"]):
        raise SystemExit("HOLD: target source row text changed; cannot verify")
    result={
      "status":"CANDIDATE_SOURCE_IDENTIFIED_NOT_LINKED",
      "publish_allowed":False,
      "unresolved_row_id":MISSING_ROW_ID,
      "observed_missing_row_date":"2026-08-31",
      "observed_missing_row_amount":None,
      "possible_official_source":OFFICIAL_URL,
      "possible_official_source_sha256":observed,
      "possible_source_rows":located,
      "source_confirmed_amount_krw":25500,
      "match_authorized":False,
      "reason":"matching calendar date does not establish row identity or official file provenance",
      "needed_evidence":["failed row original source_attachment_url","failed row source_sheet","failed row source_row","failed row merchant/purpose"],
      "source_original_provenance":"GitHub Actions original official capture run 41579798147"
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="possible_source_rows"},ensure_ascii=False))

if __name__=="__main__":
    main()
