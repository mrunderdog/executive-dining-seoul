#!/usr/bin/env python3
"""Read-only forensic capture of *observed* official Incheon Council attachments.

URLs/expected SHA hashes come from the committed 2026-10 baseline official
discovery and raw file inventory. The only unpinned file (1321) was present
as a concrete official URL in the discovery ledger, but had not been hashed.
No unpublished data, publication actions, or inferred values are used.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"pipeline"))
from ingest_council_expense import fetch_binary, workbook_rows, normalize_sheet

TARGETS = {
    # 2026-08 public council posts, independently verified from official detail pages:
    # 1314 Education / 1315 Urban Construction / 1318 Public Administration
    1314: (None, 8),
    1315: (None, 8),
    1318: (None, 8),
    1320: ("d85541d349a5f5e20fb4023be5c34093ad59a7e80483a3409af2c61143ef6dcb", 8),
    1321: (None, 8),  # explicit 2026-08 official posting from discovery
    1322: ("4856197cef57cff59e5ecb3825e7fad9ed1a88697222a9bdc2da7d1d03bd43f3", 9),
    1323: ("860248268daf693651bff18e8a3c737acbeb7d123e09629f041ac4540e0d21e8", 9),
    1326: ("e1459b54a55c040caa86af3f5fcc582a630543b79cf6030acc86f96153a97e1e", 9),
    1327: ("44129be489aee23846fa19c4e0de465ef105164be42f74e2a1fe99c06d5b89dd", 9),
}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--msg-seq",type=int,choices=sorted(TARGETS),required=True)
    ap.add_argument("--strict-parse",action="store_true")
    a=ap.parse_args()
    seq=a.msg_seq
    expected,month=TARGETS[seq]
    url=f"https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&fileno=1&msg_seq={seq}"
    post=f"https://www.icouncil.go.kr/main/bbs/bbsMsgDetail.do?msg_seq={seq}&bcd=infordisc&pgno=1"
    dest=ROOT/f"reports/recovery/incheon-official-{seq}"
    dest.mkdir(parents=True,exist_ok=True)
    report={"source":"incheon_council","seq":seq,"official_post":post,
            "official_file":url,"expected_sha256":expected,"period":[2026,month,None],
            "publication":"NOT_PERFORMED"}
    try:
        blob=fetch_binary(url,post)
        observed=hashlib.sha256(blob).hexdigest()
        report.update(observed_sha256=observed,file_bytes=len(blob),
                      header=blob[:16].hex())
        if expected and observed!=expected:
            raise ValueError("official attachment SHA differs from committed source baseline")
        if blob.startswith(b"%PDF"):
            ext="pdf"
        elif blob.startswith(b"PK"):
            ext="xlsx"
        else:
            raise ValueError("official endpoint returned unrecognized file format")
        (dest/f"official-{seq}.{ext}").write_bytes(blob)
        report["format"]=ext
        pages=[]
        if ext=="pdf":
            from pypdf import PdfReader
            reader=PdfReader(io.BytesIO(blob))
            report["page_count"]=len(reader.pages)
            for pi,page in enumerate(reader.pages,1):
                try:
                    layout=page.extract_text(extraction_mode="layout") or ""
                except TypeError:
                    layout=page.extract_text() or ""
                plain=page.extract_text() or ""
                pages.append({"page":pi,"layout_text":layout,"plain_text":plain})
        sections=[]
        for name, rows in workbook_rows(blob,f"official-{seq}.{ext}"):
            meta={"source":"incheon_council","region":"인천","jurisdiction":"인천광역시",
                  "institution":"인천광역시의회","post_url":post,
                  "attachment_url":url,"attachment_name":f"official-{seq}.{ext}",
                  "attachment_sha256":observed,"period":[2026,month,None],
                  "default_role":""}
            candidates, info=normalize_sheet(rows,name,meta)
            sections.append({"name":name,"row_count":len(rows),
                             "original_rows":[{"n":i+1,"cells":[str(c)[:600] for c in row[:18]]}
                                              for i,row in enumerate(rows[:130])],
                             "parser":info,"normalized_count":len(candidates),
                             "normalized_samples":[{k:r.get(k) for k in
                                ("row_id","source_row","used_date","amount","merchant",
                                 "purpose","role","source_sheet")}
                                for r in candidates[:150]]})
        report["sections"]=sections
        if a.strict_parse:
            from incheon_verified_pdf import VERIFIED
            spec=VERIFIED.get(observed)
            actual={s["name"]:s["normalized_count"] for s in sections}
            statuses=[s["parser"].get("status") for s in sections]
            if not spec or actual!=spec[3] or any(x!="OK" for x in statuses):
                raise ValueError(f"verified PDF pages mismatch: source={seq} expected={spec[3] if spec else None} actual={actual} statuses={statuses}")
        report["pdf_pages"]=pages
        report["status"]="CAPTURED_BASELINE_SHA_OK" if expected else "CAPTURED_NEW_OFFICIAL_UNPINNED"
    except Exception as exc:
        report["status"]="HOLD"
        report["error"]=f"{type(exc).__name__}: {exc}"
    (dest/"evidence.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("sections","pdf_pages")},
                     ensure_ascii=False,indent=2),flush=True)
    if report["status"]=="HOLD":
        raise SystemExit(2)

if __name__=="__main__":
    main()
