#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from ingest_council_expense import fetch_binary, workbook_rows, normalize_sheet, clean_text

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/"reports"
RAW_DIR=ROOT/"data"/"raw"
DISCOVERY=REPORTS/"gyeonggi-executive-discovery.json"


def main():
    if not DISCOVERY.exists():
        raise SystemExit(f"missing discovery report: {DISCOVERY}")
    d=json.loads(DISCOVERY.read_text(encoding="utf-8"))
    posts=d.get("posts") or []
    if not posts:
        raise SystemExit("no Gyeonggi posts to ingest")

    all_rows=[]; files=[]; errors=[]
    for post in posts:
        for att in post.get("attachments") or []:
            url=att.get("url") or ""
            if not url: continue
            name=clean_text(att.get("text")) or url.rsplit("/",1)[-1]
            try:
                blob=fetch_binary(url)
                per_file={
                    "title":post.get("title"),"department":post.get("department"),
                    "url":url,"name":name,"bytes":len(blob),
                    "sha256":hashlib.sha256(blob).hexdigest(),"sheets":[]
                }
                for sheet_name,rows in workbook_rows(blob,name):
                    meta={
                        "source":"gyeonggi_province",
                        "region":"경기","jurisdiction":"경기도","institution":"경기도청",
                        "post_url":post.get("post_url"),"attachment_url":url,
                        "attachment_name":name,"period":post.get("period"),
                    }
                    normalized,info=normalize_sheet(rows,sheet_name,meta)
                    department=clean_text(post.get("department")) or clean_text(post.get("title"))
                    for r in normalized:
                        r["department"]=department
                        # Most departmental spreadsheets have no actor column; retain the
                        # department lineage instead of a generic Sheet1 role.
                        if not clean_text(r.get("role")) or clean_text(r.get("role")).lower().startswith("sheet"):
                            r["role"]=department
                    per_file["sheets"].append(info)
                    all_rows.extend(normalized)
                files.append(per_file)
            except Exception as e:
                errors.append({"post":post.get("title"),"url":url,"error":f"{type(e).__name__}: {e}"})

    unique={r["row_id"]:r for r in all_rows}
    rows=sorted(unique.values(),key=lambda r:(r.get("used_date") or "",r.get("department") or "",r["row_id"]))
    payload={
        "schema_version":1,
        "source":"gyeonggi_province",
        "generated_at":datetime.now().isoformat(timespec="seconds"),
        "row_count":len(rows),
        "rows":rows,
        "files":files,
        "errors":errors,
    }
    RAW_DIR.mkdir(exist_ok=True)
    out=RAW_DIR/"gyeonggi_province_expense.json"
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

    md=[
        "# Gyeonggi Province expense ingestion","",
        f"- Normalized rows: **{len(rows)}**",
        f"- Files: **{len(files)}**",
        f"- Errors: **{len(errors)}**","",
        "## Files","",
    ]
    for f in files:
        md.append(f"- {f.get('department') or '-'} — `{f.get('name','')[:120]}` — {sum(s.get('parsed_rows',0) for s in f.get('sheets',[]))} rows")
    if errors:
        md+=["","## Errors",""]
        md.extend(f"- {e}" for e in errors)
    (REPORTS/"gyeonggi-province-ingestion.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"rows":len(rows),"files":len(files),"errors":len(errors)},ensure_ascii=False))
    if not rows:
        raise SystemExit("Gyeonggi ingestion produced no rows")


if __name__=="__main__":
    main()
