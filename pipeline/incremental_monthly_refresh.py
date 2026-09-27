#!/usr/bin/env python3
"""Incremental monthly council refresh.

Discovers only a recent window, skips attachments already present in each raw
file, and isolates source failures so one council cannot block publication.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from capital_backfill import SOURCES

ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/"reports"/"incremental-council-status.json"


def month_shift(y:int,m:int,delta:int)->tuple[int,int]:
    n=y*12+(m-1)+delta
    return n//12,n%12+1


def run(cmd:list[str],timeout:int=180)->tuple[bool,str]:
    try:
        p=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
        return p.returncode==0,p.stdout[-8000:]
    except subprocess.TimeoutExpired as e:
        out=(e.stdout or "")
        if isinstance(out,bytes): out=out.decode(errors="replace")
        return False,f"TIMEOUT after {timeout}s\n{out[-4000:]}"


def git_head_bytes(path:str)->bytes|None:
    p=subprocess.run(["git","show",f"HEAD:{path}"],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    return p.stdout if p.returncode==0 else None


def restore_source(source:str):
    paths=[
        f"data/raw/{source}_expense.json",
        f"reports/{source}-executive-candidates.json",
        f"reports/{source}-executive-candidates.md",
        f"reports/{source}-ingestion.md",
    ]
    for rel in paths:
        payload=git_head_bytes(rel)
        p=ROOT/rel
        if payload is None:
            if p.exists(): p.unlink()
        else:
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(payload)


def refresh_one(source:str,since:str,until:str)->dict:
    result={"source":source,"status":"UNKNOWN","stages":{}}
    stages=[
        ("discovery",[sys.executable,"pipeline/capital_backfill.py","--since",since,"--until",until,"--source",source],90),
        ("ingest",[sys.executable,"pipeline/ingest_council_expense.py","--source",source,"--incremental"],150),
        ("dates",[sys.executable,"pipeline/repair_raw_dates.py","--source",source,"--min-valid","0.95"],45),
        ("candidates",[sys.executable,"pipeline/build_source_candidates.py","--source",source,"--top","100"],45),
    ]
    for name,cmd,timeout in stages:
        ok,out=run(cmd,timeout)
        result["stages"][name]={"ok":ok,"tail":out[-1500:]}
        if not ok:
            restore_source(source)
            result["status"]=f"STALE_OK:{name.upper()}" if (ROOT/f"data/raw/{source}_expense.json").exists() else f"FAILED:{name.upper()}"
            return result
    # Detect the fast no-change path from ingestor output for observability.
    ingest_tail=result["stages"]["ingest"]["tail"]
    result["status"]="NO_CHANGE" if '"status": "NO_CHANGE"' in ingest_tail or '"status":"NO_CHANGE"' in ingest_tail else "UPDATED"
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--lookback-months",type=int,default=5,
                    help="Inclusive recent publication period window. 5 catches late quarterly postings.")
    ap.add_argument("--workers",type=int,default=6)
    ap.add_argument("--source",action="append",dest="sources")
    args=ap.parse_args()

    today=date.today()
    sy,sm=month_shift(today.year,today.month,-max(0,args.lookback_months-1))
    since=f"{sy:04d}-{sm:02d}"
    until=f"{today.year:04d}-{today.month:02d}"
    known={s.key for s in SOURCES}
    selected=args.sources or [s.key for s in SOURCES]
    bad=[s for s in selected if s not in known]
    if bad: raise SystemExit(f"unknown sources: {bad}")

    results=[]
    with ThreadPoolExecutor(max_workers=max(1,min(args.workers,8))) as pool:
        futs={pool.submit(refresh_one,s,since,until):s for s in selected}
        for fut in as_completed(futs):
            source=futs[fut]
            try: r=fut.result()
            except Exception as e:
                restore_source(source)
                r={"source":source,"status":"STALE_OK:WORKER","error":f"{type(e).__name__}: {e}","stages":{}}
            results.append(r)
            print(json.dumps({"source":r["source"],"status":r["status"]},ensure_ascii=False),flush=True)

    order={s:i for i,s in enumerate(selected)}
    results.sort(key=lambda x:order.get(x["source"],999))
    summary={
        "mode":"incremental",
        "since":since,"until":until,
        "sources":len(results),
        "updated":sum(r["status"]=="UPDATED" for r in results),
        "no_change":sum(r["status"]=="NO_CHANGE" for r in results),
        "stale_ok":sum(r["status"].startswith("STALE_OK:") for r in results),
        "failed":sum(r["status"].startswith("FAILED:") for r in results),
        "results":results,
    }
    STATUS.parent.mkdir(exist_ok=True)
    STATUS.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k!="results"},ensure_ascii=False,indent=2))
    if summary["failed"]:
        raise SystemExit(f"{summary['failed']} source(s) have no usable fallback")


if __name__=="__main__":
    main()
