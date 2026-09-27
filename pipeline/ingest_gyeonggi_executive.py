#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
    ap=argparse.ArgumentParser()
    ap.add_argument("--incremental",action="store_true")
    args=ap.parse_args()
    if not DISCOVERY.exists():
        raise SystemExit(f"missing discovery report: {DISCOVERY}")
    d=json.loads(DISCOVERY.read_text(encoding="utf-8"))
    posts=d.get("posts") or []
    if not posts:
        raise SystemExit("no Gyeonggi posts to ingest")

    RAW_DIR.mkdir(exist_ok=True)
    out=RAW_DIR/"gyeonggi_province_expense.json"
    previous={}
    if args.incremental and out.exists():
        try: previous=json.loads(out.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError): previous={}
    previous_rows=list(previous.get("rows",[]))
    previous_files=list(previous.get("files",[]))
    previous_errors=list(previous.get("errors",[]))
    known_urls={str(f.get("url") or "") for f in previous_files if f.get("url")}

    all_rows=[]; files=[]; errors=[]
    for post in posts:
        for att in post.get("attachments") or []:
            url=att.get("url") or ""
            if not url: continue
            if args.incremental and url in known_urls: continue
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
                        r["row_id"]=hashlib.sha256(
                            "|".join(str(r.get(k,"")) for k in (
                                "institution","department","used_date","role","merchant","amount",
                                "source_attachment_name","source_sheet","source_row"
                            )).encode("utf-8")
                        ).hexdigest()[:20]
                    per_file["sheets"].append(info)
                    all_rows.extend(normalized)
                files.append(per_file)
            except Exception as e:
                errors.append({"post":post.get("title"),"url":url,"error":f"{type(e).__name__}: {e}"})

    if args.incremental and not files and not errors:
        print(json.dumps({"status":"NO_CHANGE","rows":len(previous_rows),"known_files":len(previous_files)},ensure_ascii=False))
        return

    unique={r["row_id"]:r for r in previous_rows+all_rows}
    rows=sorted(unique.values(),key=lambda r:(r.get("used_date") or "",r.get("department") or "",r["row_id"]))
    if not rows:
        raise SystemExit("Gyeonggi executive ingestion produced no rows")

    success_urls={str(f.get("url") or "") for f in files if f.get("url")}
    file_map={str(f.get("url") or ""):f for f in previous_files if f.get("url")}
    for f in files:
        if f.get("url"): file_map[str(f["url"])]=f
    merged_files=list(file_map.values()) if args.incremental else files
    merged_errors=[e for e in previous_errors if str(e.get("url") or "") not in success_urls] if args.incremental else []
    seen={(str(e.get("url") or ""),str(e.get("error") or "")) for e in merged_errors}
    for e in errors:
        key=(str(e.get("url") or ""),str(e.get("error") or ""))
        if key not in seen: merged_errors.append(e);seen.add(key)
    merged_errors=merged_errors[-100:] if args.incremental else errors

    payload={
        "schema_version":1,
        "source":"gyeonggi_province",
        "generated_at":datetime.now().isoformat(timespec="seconds"),
        "refresh_mode":"incremental" if args.incremental else "full",
        "new_files":len(files),
        "row_count":len(rows),"rows":rows,
        "files":merged_files,"errors":merged_errors,
    }
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    files=merged_files;errors=merged_errors

    md=[
        "# Gyeonggi Province expense ingestion","",
        f"- Normalized rows: **{len(rows)}**",
        f"- Refresh mode: **{'incremental' if args.incremental else 'full'}**",
        f"- New files: **{payload.get('new_files', len(files))}**",
        f"- Files retained: **{len(files)}**",
        f"- Errors: **{len(errors)}**","",
        "## Files","",
    ]
    for f in files:
        md.append(f"- {f.get('department') or '-'} — `{f.get('name','')[:120]}` — {sum(s.get('parsed_rows',0) for s in f.get('sheets',[]))} rows")
    if errors:
        md+=["","## Errors",""]
        md.extend(f"- {e}" for e in errors)
    (REPORTS/"gyeonggi-province-ingestion.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"status":"UPDATED" if payload.get("new_files") else "RETRIED_ERRORS","rows":len(rows),"new_files":payload.get("new_files"),"files":len(files),"errors":len(errors)},ensure_ascii=False))
    if not rows:
        raise SystemExit("Gyeonggi ingestion produced no rows")


if __name__=="__main__":
    main()
