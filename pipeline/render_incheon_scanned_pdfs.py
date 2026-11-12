#!/usr/bin/env python3
"""Render two SHA-pinned image-only official Incheon council PDFs for review.

No OCR or transaction inference. Output original page PNGs and SHA evidence.
Source is restricted to official URLs previously independently SHA-verified.
"""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path

from ingest_council_expense import fetch_binary

ROOT=Path(__file__).resolve().parents[1]
TARGETS={
  1321:"1ed8414992e06999cfb60c12e23c1d72ccff041941007aa0145012cb4c5a927e",
  1329:"81e2d85f2dd0c5c43463da8e34fa724d38223790921f657c49a2fb480886e264",
}
def render(*, fetch=fetch_binary):
    import fitz
    out=ROOT/"reports/recovery/incheon-scanned-pages"
    out.mkdir(parents=True,exist_ok=True)
    findings=[]
    for seq,expected in TARGETS.items():
        url=f"https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&fileno=1&msg_seq={seq}"
        referer=f"https://www.icouncil.go.kr/main/bbs/bbsMsgDetail.do?bcd=infordisc&msg_seq={seq}"
        record={"msg_seq":seq,"official_url":url,"expected_sha256":expected,
                "status":"HOLD","page_images":[]}
        findings.append(record)
        try:
            blob=fetch(url,referer)
            observed=hashlib.sha256(blob).hexdigest()
            record.update({"observed_sha256":observed,"bytes":len(blob)})
            if observed!=expected or not blob.startswith(b"%PDF"):
                record["reason"]="official_original_changed_or_not_pdf"
                continue
            doc=fitz.open(stream=blob,filetype="pdf")
            record["pdf_pages"]=len(doc)
            for n,page in enumerate(doc):
                name=f"incheon-{seq}-page-{n+1}.png"
                page.get_pixmap(matrix=fitz.Matrix(2.5,2.5),alpha=False).save(str(out/name))
                record["page_images"].append(name)
            record["status"]="ORIGINAL_PAGES_RENDERED_REVIEW_REQUIRED"
        except Exception as exc:
            record["reason"]=type(exc).__name__
    (out/"manifest.json").write_text(
        json.dumps({"source":"incheon_council","purpose":"human scanned-page verification only",
                    "publish":False,"files":findings},ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8")
    for rec in findings:
        print(json.dumps(rec,ensure_ascii=False),flush=True)
    return findings

if __name__=="__main__":
    render()
