#!/usr/bin/env python3
"""Compare observed 2026-08-31 official Incheon Council source rows.

This evidence is NOT a recovered failing row. A date match is insufficient:
candidate e6256a2ab172f5fd2ac7 lacks captured source attachment, page and
source row from the original failed live ingest. Keep the row HOLD.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

OFFICIAL_SHA = {
    1314: "d5b82cd30b00e03958538759803afb2354472b0cfbb4b2fa99cd9111444117cf",
    1315: "1154932076166a94b96870f0abec29a044c5361f3dfa8c792052d10704b7484a",
    1318: "b2d2abd9fb4cd85d818070ba6ee9013b4f2dc22cb7e510d0eeaa97f0e8547def",
    1320: "d85541d349a5f5e20fb4023be5c34093ad59a7e80483a3409af2c61143ef6dcb",
}
TARGET_ROW="e6256a2ab172f5fd2ac7"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--artifacts",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    candidate_rows=[]
    source_status=[]
    for seq,expected_sha in OFFICIAL_SHA.items():
        base=args.artifacts/f"incheon-original-{seq}"
        receipt=base/"evidence.json"
        pdf=base/f"official-{seq}.pdf"
        if not receipt.is_file() or not pdf.is_file():
            raise SystemExit(f"HOLD: missing original artifact {seq}")
        d=json.loads(receipt.read_text(encoding="utf-8"))
        sha=hashlib.sha256(pdf.read_bytes()).hexdigest()
        url=f"https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&fileno=1&msg_seq={seq}"
        if (sha!=expected_sha or d.get("observed_sha256")!=sha
            or d.get("official_file")!=url
            or d.get("status") not in {"CAPTURED_NEW_OFFICIAL_UNPINNED","CAPTURED_BASELINE_SHA_OK"}):
            raise SystemExit(f"HOLD: official source receipt or SHA differs {seq}")
        all_found=0
        for sec in d.get("sections",[]):
            for row in sec.get("original_rows",[]):
                cells=row.get("cells",[])
                joined=" ".join(map(str,cells))
                if not re.search(r"2026[.\-/]\s*0?8[.\-/]\s*31\b",joined):
                    continue
                all_found+=1
                candidate_rows.append({
                    "seq":seq,"source_sha256":sha,"source_file":url,
                    "source_sheet":sec["name"],"source_row":row["n"],
                    "source_cells":cells,
                })
        source_status.append({"seq":seq,"original_sha256":sha,"aug31_rows":all_found})
    result={
        "status":"PROVENANCE_NOT_YET_LINKED",
        "publication_authorized":False,
        "failed_row_id":TARGET_ROW,
        "failed_date":"2026-08-31",
        "failed_amount":None,
        "comparison_scope":"four exact observed August public attachments only",
        "source_status":source_status,
        "aug31_official_rows":candidate_rows,
        "reason":"Original failed candidate did not retain source_attachment_url, source_sheet and source_row. Matching date is insufficient; none is an authorized correction.",
        "required_next":"Capture failed candidate complete row and file lineage on fresh live ingest, compare source URL/page/row, and prove original amount without inference."
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="aug31_official_rows"},ensure_ascii=False))
    print(f"Observed official 2026-08-31 candidate source rows: {len(candidate_rows)}; no auto correction.")

if __name__=="__main__":
    main()
