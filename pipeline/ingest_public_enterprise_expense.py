#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import Counter
from datetime import datetime
from pathlib import Path

from ingest_central_executive_expense import parse_attachment

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/"reports"
RAW_DIR=ROOT/"data"/"raw"
DISCOVERY=REPORTS/"public-enterprise-discovery.json"

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--incremental",action="store_true");args=ap.parse_args()
    if not DISCOVERY.exists():raise SystemExit("run public_enterprise_discovery.py first")
    d=json.loads(DISCOVERY.read_text(encoding="utf-8"))
    RAW_DIR.mkdir(exist_ok=True)
    out=RAW_DIR/"public_enterprise_expense.json"
    previous={}
    if args.incremental and out.exists():
        try:previous=json.loads(out.read_text(encoding="utf-8"))
        except Exception:previous={}
    previous_rows=list(previous.get("rows",[]));previous_files=list(previous.get("files",[]));previous_errors=list(previous.get("errors",[]))
    known={str(x.get("url") or "") for x in previous_files if x.get("url")}
    rows=[];files=[];errors=[]
    for src in d.get("sources",[]):
        if src.get("status")=="TRACK_ONLY":continue
        for a in src.get("attachments",[]):
            url=str(a.get("url") or "")
            if not url or (args.incremental and url in known):continue
            parsed,info,error=parse_attachment(src,a)
            rows.extend(parsed)
            if info:files.append(info)
            if error:errors.append(error)
    if args.incremental and not files and not errors:
        print(json.dumps({"status":"NO_CHANGE","rows":len(previous_rows),"known_files":len(previous_files)},ensure_ascii=False));return
    unique={r["row_id"]:r for r in previous_rows+rows}
    merged_rows=sorted(unique.values(),key=lambda r:(r.get("used_date") or "",r.get("institution") or "",r["row_id"]))
    fmap={str(x.get("url") or ""):x for x in previous_files if x.get("url")}
    for x in files:
        if x.get("url"):fmap[str(x["url"])]=x
    merged_files=list(fmap.values()) if args.incremental else files
    merged_errors=(previous_errors+errors)[-100:] if args.incremental else errors
    if not args.incremental and not merged_rows and out.exists():
        print(json.dumps({"status":"STALE_OK:EMPTY_FULL","reason":"fresh refresh returned zero rows; last-good preserved"},ensure_ascii=False));return
    payload={"schema_version":1,"generated_at":datetime.now().isoformat(timespec="seconds"),"refresh_mode":"incremental" if args.incremental else "full","row_count":len(merged_rows),"rows":merged_rows,"files":merged_files,"errors":merged_errors}
    out.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    cc=Counter(r.get("institution") or "(unknown)" for r in merged_rows)
    md=["# Public-enterprise leadership expense ingestion","",f"- Rows: **{len(merged_rows)}**",f"- Files: **{len(merged_files)}**",f"- Errors: **{len(merged_errors)}**","","## Rows by institution",""]
    for k,v in cc.most_common():md.append(f"- {k}: {v}")
    (REPORTS/"public-enterprise-ingestion.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"status":"UPDATED","rows":len(merged_rows),"new_files":len(files),"files":len(merged_files),"errors":len(merged_errors),"institutions":len(cc)},ensure_ascii=False))

if __name__=="__main__":main()
