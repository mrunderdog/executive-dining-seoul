#!/usr/bin/env python3
"""Read-only forensics for Incheon Council officially downloadable expense PDFs.

Unchanged data/raw; report is a candidate for human source-page reconciliation.
Never substitute a guessed amount or silently drop a scanned/unsupported PDF.
"""
import hashlib
import io
import json
from pathlib import Path

from ingest_council_expense import (
    fetch_binary, workbook_rows, normalize_sheet, clean_text, infer_pdf_context_role
)

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    1320: ("2026-08", "환경교통위원장"),
    1321: ("2026-08", "문화복지위원장"),
    1322: ("2026-09", "도시건설위원장"),
    1323: ("2026-09", "교육위원장"),
    1326: ("2026-09", "의회운영위원장"),
    1327: ("2026-09", "환경교통위원장"),
    1329: ("2026-09", "문화복지위원장"),
    1330: ("2026-09", "산업경제위원장"),
}
def main():
    docs=[]
    for seq, (month, role) in TARGETS.items():
        url=("https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?"
             f"bcd=infordisc&fileno=1&msg_seq={seq}")
        post=("https://www.icouncil.go.kr/main/bbs/bbsMsgDetail.do?"
              f"bcd=infordisc&msg_seq={seq}")
        record={"msg_seq":seq,"role":role,"period":month,"url":url,
                "pages":[],"transactions":[],"exceptions":[]}
        docs.append(record)
        try:
            blob=fetch_binary(url,post)
            record["sha256"]=hashlib.sha256(blob).hexdigest()
            record["bytes"]=len(blob)
            record["magic"]=blob[:8].hex()
            if not blob.startswith(b"%PDF"):
                record["exceptions"].append("non_pdf_official_response")
                continue
            from pypdf import PdfReader
            reader=PdfReader(io.BytesIO(blob))
            record["pdf_page_count"]=len(reader.pages)
            record["page_image_counts"]=[len(p.images) for p in reader.pages]
            for sheet_name,rows in workbook_rows(blob,f"{seq}.pdf"):
                page={"sheet":sheet_name,"extracted_line_count":len(rows),
                      "line_sample":[{"source_row":i+1,"cells":[clean_text(c) for c in row]}
                                     for i,row in enumerate(rows[:19])],
                      "aug_31_lines":[{"source_row":i+1,"cells":[clean_text(c) for c in row]}
                                      for i,row in enumerate(rows)
                                      if "08-31" in " ".join(map(str,row)) or "08.31" in " ".join(map(str,row))]}
                meta={"source":"incheon_council","region":"인천",
                      "jurisdiction":"인천광역시","institution":"인천광역시의회",
                      "post_url":post,"attachment_url":url,
                      "attachment_name":f"{seq}.pdf",
                      "attachment_sha256":record["sha256"],
                      "period":[int(month[:4]),int(month[-2:]),None],
                      "default_role":role}
                try:
                    normalized,info=normalize_sheet(rows,sheet_name,meta)
                    page["current_parser"]=info
                    page["normalized_count"]=len(normalized)
                    record["transactions"] += [{
                        "row_id":r.get("row_id"),"source_row":r.get("source_row"),
                        "date":r.get("used_date"),"merchant":r.get("merchant"),
                        "amount":r.get("amount"),"role":r.get("role")}
                        for r in normalized]
                except Exception as exc:
                    page["parser_exception"]=f"{type(exc).__name__}: {exc}"
                record["pages"].append(page)
        except Exception as exc:
            record["exceptions"].append(f"{type(exc).__name__}: {exc}")
        record["parsed_count"]=len(record["transactions"])
    out=ROOT/"reports/recovery/incheon-forensics"
    out.mkdir(parents=True,exist_ok=True)
    (out/"official_pdf_diagnostics.json").write_text(
        json.dumps({"source":"incheon_council","baseline_untouched":True,"documents":docs},
                   ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for doc in docs:
        print(json.dumps({"msg_seq":doc["msg_seq"],"sha":doc.get("sha256"),
                          "bytes":doc.get("bytes"),"pdf_pages":doc.get("pdf_page_count"),
                          "page_images":doc.get("page_image_counts"),
                          "page_results":[{"sheet":p["sheet"],"status":p.get("current_parser",{}).get("status"),
                                           "parsed":p.get("normalized_count"),
                                           "lines":p["extracted_line_count"],
                                           "aug31":p.get("aug_31_lines",[])}
                                          for p in doc["pages"]],
                          "parsed_count":doc.get("parsed_count"),
                          "errors":doc["exceptions"]},ensure_ascii=False),flush=True)
if __name__=="__main__":
    main()
