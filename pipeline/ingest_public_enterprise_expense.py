#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    rows=[];files=[];errors=[];jobs=[]
    for src in d.get("sources",[]):
        if src.get("status")=="TRACK_ONLY":continue
        for a in src.get("attachments",[]):
            url=str(a.get("url") or "")
            if not url or (args.incremental and url in known):continue
            jobs.append((src,a))
    if jobs:
        with ThreadPoolExecutor(max_workers=min(4,len(jobs))) as pool:
            future_map={pool.submit(parse_attachment,src,a):(src,a) for src,a in jobs}
            for fut in as_completed(future_map):
                parsed,info,error=fut.result()
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
    if not args.incremental and out.exists():
        try:baseline=json.loads(out.read_text(encoding="utf-8"))
        except Exception:baseline={}
        baseline_rows=list(baseline.get("rows",[]))
        baseline_files=list(baseline.get("files",[]))
        if not merged_rows:
            print(json.dumps({"status":"STALE_OK:EMPTY_FULL","baseline_rows":len(baseline_rows),"reason":"fresh refresh returned zero rows; last-good preserved"},ensure_ascii=False));return

        # Protect each existing institution independently. A new institution
        # must not hide a partial outage at an older source by making the total
        # row count look healthy.
        baseline_counts=Counter(r.get("institution") or "(unknown)" for r in baseline_rows)
        fresh_counts=Counter(r.get("institution") or "(unknown)" for r in merged_rows)
        degraded={
            inst for inst,old_count in baseline_counts.items()
            if old_count and fresh_counts.get(inst,0) < max(1,int(old_count*0.85))
        }
        if degraded:
            # Replace the degraded institution wholesale with its committed
            # last-good rows. Mixing partial fresh rows with baseline rows can
            # double-count the same transactions when source row numbers or
            # sheet labels change between downloads.
            healthy_rows=[
                r for r in merged_rows
                if (r.get("institution") or "(unknown)") not in degraded
            ]
            restored_rows=[
                r for r in baseline_rows
                if (r.get("institution") or "(unknown)") in degraded
            ]
            row_map={r["row_id"]:r for r in healthy_rows+restored_rows}
            merged_rows=sorted(row_map.values(),key=lambda r:(r.get("used_date") or "",r.get("institution") or "",r["row_id"]))

            healthy_files=[
                x for x in merged_files
                if (x.get("institution") or "(unknown)") not in degraded
            ]
            restored_files=[
                x for x in baseline_files
                if (x.get("institution") or "(unknown)") in degraded
            ]
            file_map={str(x.get("url") or ""):x for x in healthy_files+restored_files if x.get("url")}
            merged_files=list(file_map.values())
            print(json.dumps({
                "status":"PARTIAL_STALE_OK",
                "institutions":sorted(degraded),
                "baseline_counts":{k:baseline_counts[k] for k in sorted(degraded)},
                "fresh_counts":{k:fresh_counts.get(k,0) for k in sorted(degraded)},
                "reason":"degraded institutions restored from last-good while healthy/new institutions remain fresh"
            },ensure_ascii=False))
    payload={"schema_version":1,"generated_at":datetime.now().isoformat(timespec="seconds"),"refresh_mode":"incremental" if args.incremental else "full","row_count":len(merged_rows),"rows":merged_rows,"files":merged_files,"errors":merged_errors}
    out.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    cc=Counter(r.get("institution") or "(unknown)" for r in merged_rows)
    md=["# Public-enterprise leadership expense ingestion","",f"- Rows: **{len(merged_rows)}**",f"- Files: **{len(merged_files)}**",f"- Errors: **{len(merged_errors)}**","","## Rows by institution",""]
    for k,v in cc.most_common():md.append(f"- {k}: {v}")
    (REPORTS/"public-enterprise-ingestion.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"status":"UPDATED","rows":len(merged_rows),"new_files":len(files),"files":len(merged_files),"errors":len(merged_errors),"institutions":len(cc)},ensure_ascii=False))

if __name__=="__main__":main()
