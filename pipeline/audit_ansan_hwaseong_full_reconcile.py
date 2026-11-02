#!/usr/bin/env python3
"""Source-isolated 2026-11 Ansan/Hwaseong Full Refresh QA audit.

Never stages/commits any raw file. Records whether failures originate in
official discovery, attachment parsing, immutable-history checks, or strict
new-record QA. Existing records remain the authoritative baseline.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, hashlib
from pathlib import Path
from collections import Counter,defaultdict

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"pipeline"))
from capital_backfill import canonical_attachment_url
from qa_council_publication import assess_incremental, period_bounds
from guard_full_council import check_discovery,check_integrity
from ingest_council_expense import valid_transaction_merchant
from datetime import date

def git_json(path):
    p=subprocess.run(["git","show",f"HEAD:{path}"],cwd=ROOT,capture_output=True,text=True)
    return json.loads(p.stdout) if p.returncode==0 else {}

def run(argv,seconds):
    try:
        p=subprocess.run([sys.executable,*argv],cwd=ROOT,capture_output=True,text=True,timeout=seconds)
        return {"rc":p.returncode,"argv":argv,"out":p.stdout[-26000:],"err":p.stderr[-5000:]}
    except subprocess.TimeoutExpired as exc:
        return {"rc":124,"argv":argv,"out":str(exc.stdout or b"")[-3000:],
                "err":"TIMEOUT "+str(seconds)}

def failures_for(row):
    out=[]
    try:d=date.fromisoformat(str(row.get("used_date") or ""))
    except (TypeError,ValueError):d=None
    p=period_bounds(row.get("source_period"))
    if d is None:out.append("invalid_date")
    elif p is None or not p[0]<=d<=p[1]:out.append("out_of_period")
    a=row.get("amount")
    if not isinstance(a,(int,float)) or isinstance(a,bool) or not 0<a<50_000_000:
        out.append("amount_invalid")
    if not valid_transaction_merchant(row.get("merchant")):out.append("merchant_invalid")
    if not canonical_attachment_url(row.get("source_attachment_url")):
        out.append("attachment_invalid")
    return out

def main(source):
    prefix=f"reports/p1-ansan-hwaseong-qa/{source}"
    target=ROOT/(prefix+".json")
    target.parent.mkdir(parents=True,exist_ok=True)
    raw=f"data/raw/{source}_expense.json"
    discovery=f"reports/capital-backfill-discovery-{source}.json"
    baseline=git_json(raw)
    previous_discovery=git_json(discovery)
    result={"source":source,"baseline_rows":len(baseline.get("rows",[])),
            "baseline_files":len(baseline.get("files",[])),
            "baseline_row_id_digest":hashlib.sha256(json.dumps(baseline.get("rows",[]),sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
            "stages":[],"status":"NOT_STARTED"}
    def write():
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
        print("AUDIT_RESULT "+json.dumps({k:result.get(k) for k in
                  ("source","status","baseline_rows","baseline_files","new_rows","new_files","qa","integrity","discovery_guard") if k in result},ensure_ascii=False,default=str)[:15000],flush=True)
    steps=[(["pipeline/capital_backfill.py","--since","2024-12","--until","2026-11","--source",source],210,"DISCOVERY"),
          (["pipeline/guard_full_council.py","--source",source,"--phase","discovery","--baseline-ref","HEAD"],70,"DISCOVERY_GUARD"),
          (["pipeline/ingest_council_expense.py","--source",source,"--incremental"],240,"INGEST"),
          (["pipeline/repair_raw_dates.py","--source",source,"--min-valid","0.0","--preserve-baseline-ref","HEAD"],70,"DATE_NORMALIZATION"),
          (["pipeline/guard_full_council.py","--source",source,"--phase","integrity","--baseline-ref","HEAD"],70,"INTEGRITY_GUARD")]
    for argv,timeout,stage in steps:
        p=run(argv,timeout)
        result["stages"].append({"stage":stage,**p})
        print(f"STEP {source} {stage} rc={p['rc']} "+str(p["out"][-1000:]),flush=True)
        if p["rc"]!=0:
            result["status"]="BLOCKED:"+stage
            if stage=="DISCOVERY_GUARD":
                try:result["discovery_guard"]=check_discovery(source,json.loads((ROOT/discovery).read_text()),baseline)
                except Exception:pass
            write();return
    d=json.loads((ROOT/raw).read_text(encoding="utf-8"))
    posts=json.loads((ROOT/discovery).read_text(encoding="utf-8"))
    result["discovery_guard"]=check_discovery(source,posts,baseline)
    result["integrity"]=check_integrity(source,d,baseline)
    result["qa"]=assess_incremental(source,d,posts,baseline,previous_discovery)
    oldids={r["row_id"] for r in baseline.get("rows",[])}
    oldurls={canonical_attachment_url(f.get("url")) for f in baseline.get("files",[])
             if canonical_attachment_url(f.get("url"))}
    fresh=[r for r in d.get("rows",[]) if r.get("row_id") not in oldids]
    files=[f for f in d.get("files",[]) if canonical_attachment_url(f.get("url")) not in oldurls]
    result["new_rows"]=len(fresh);result["new_files"]=len(files)
    byfile=defaultdict(list)
    for r in fresh:byfile[canonical_attachment_url(r.get("source_attachment_url"))].append(r)
    result["new_file_evidence"]=[]
    for f in files:
        k=canonical_attachment_url(f.get("url"))
        rows=byfile.get(k,[])
        problems=[{"row_id":r.get("row_id"),"used_date":r.get("used_date"),
            "source_period":r.get("source_period"),"amount":r.get("amount"),
            "merchant":r.get("merchant"),"source_sheet":r.get("source_sheet"),
            "source_row":r.get("source_row"),"errors":failures_for(r)}
            for r in rows if failures_for(r)]
        result["new_file_evidence"].append({"url":f.get("url"),"name":f.get("name"),
            "sha256":f.get("sha256"),"bytes":f.get("bytes"),
            "parsed_rows":len(rows),"bad_rows":len(problems),
            "examples":problems[:45],
            "sheet_statuses":[{"name":s.get("sheet"),"status":s.get("status"),"rows":s.get("parsed_rows"),
                               "mapping":s.get("mapping")} for s in f.get("sheets",[])]})
    result["discovered_posts"]=[{"title":p.get("title"),"period":p.get("period"),"url":p.get("post_url"),
                                  "error":p.get("error"),"attachments":len(p.get("attachments",[]))}
                                 for p in posts.get("posts",[]) if p.get("source")==source]
    result["status"]="PASS" if result["integrity"]["status"]=="PASS" and result["qa"]["status"] in ("PUBLISH_READY","NO_CHANGE") else "HOLD"
    print("SOURCE_FAILURES",json.dumps({
        "source":source,
        "new_files":[{"name":f["name"],"url":f["url"],"sha256":f["sha256"],
                      "rows":f["parsed_rows"],"bad":f["bad_rows"],
                      "examples":f["examples"][:20]} for f in result["new_file_evidence"]],
        "invalid_reason_totals":dict(Counter(reason for f in result["new_file_evidence"]
                                                for x in f["examples"] for reason in x["errors"]))
    },ensure_ascii=False)[:35000],flush=True)
    write()

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,choices=["ansan","hwaseong"])
    a=p.parse_args()
    main(a.source)
