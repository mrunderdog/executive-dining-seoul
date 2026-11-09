#!/usr/bin/env python3
"""Read-only current-main full-refresh regression for all 40 council adapters.

Runs production's full-mode discovery -> completeness guard -> incremental
ingestion -> preserve-baseline dates -> integrity guard -> strict QA -> candidates.
Each shard operates on an ephemeral GitHub Actions checkout. Never git pushes.
This is a 2026-10-31 readiness probe, NOT future December disclosure QA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/"reports"
sys.path.insert(0,str(ROOT/"pipeline"))
from capital_backfill import SOURCES

# The January full cron invokes a council source loop (not 67/73 councils).
def workflow_source_keys():
    workflow=(ROOT/".github/workflows/monthly.yml").read_text(encoding="utf-8")
    match=re.search(r"for SOURCE in ([a-z0-9_ ]+); do",workflow)
    if not match:raise RuntimeError("Full monthly source loop not found")
    return match.group(1).split()

def load_json(path):
    try:return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,ValueError):return {}

def sha(path):
    p=Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None

def registry_inventory():
    reg=load_json(ROOT/"sources/registry.json").get("sources",[])
    supplemental=load_json(ROOT/"sources/supplemental_registry.json").get("sources",[])
    sources={s.institution:s for s in SOURCES}
    full=workflow_source_keys()
    adapter_names={s.key for s in SOURCES}
    if set(full)!=adapter_names:
        raise RuntimeError(f"Full monthly source loop differs from live adapters: {set(full)^adapter_names}")
    missing_adapter=[{"institution":r.get("institution"),"region":r.get("region"),
                      "adapter":r.get("adapter"),"url":r.get("url")}
                     for r in reg if r.get("verified") and r.get("institution") not in sources]
    active_sources=[]
    for source in SOURCES:
        path=ROOT/f"data/raw/{source.key}_expense.json"
        raw=load_json(path)
        rows=raw.get("rows") or []
        dates=sorted(str(r.get("used_date")) for r in rows if re.fullmatch(r"20\d\d-\d\d-\d\d",str(r.get("used_date") or "")))
        candidates=load_json(ROOT/f"reports/{source.key}-executive-candidates.json")
        active_sources.append({"source":source.key,"institution":source.institution,
                               "region":source.region,"kind":source.kind,
                               "max_pages":source.max_pages,"has_raw_baseline":path.exists(),
                               "baseline_rows":len(rows),"baseline_files":len(raw.get("files") or []),
                               "latest_normalized_date":dates[-1] if dates else None,
                               "has_candidate_report":bool(candidates)})
    return {
        "purpose":"2027-01-15 12:00 KST full refresh readiness, observed 2026-10-31",
        "target_period_when_run":"2026-12",
        "target_period_unavailable_now":True,
        "registered_institutions":len(reg),
        "registered_verified":sum(bool(x.get("verified")) for x in reg),
        "registered_not_verified":sum(not x.get("verified") for x in reg),
        "monthly_full_council_adapters":len(full),
        "full_schedule":"0 3 15 1,4,7,10 * (03:00 UTC=12:00 KST)",
        "registered_verified_without_full_adapter":missing_adapter,
        "supplemental_registry": [
            {"key":x.get("key"),"institution":x.get("institution"),"verified":bool(x.get("verified")),
             "adapter":x.get("adapter"),"url":x.get("url")} for x in supplemental
        ],
        "sources":active_sources,
        "special_full_cohorts":[
            "Seoul City Hall OpenAPI (requires SEOUL_API_KEY secret)",
            "Gyeonggi and Incheon executive official disclosures",
            "Central executive government", "Public enterprises", "Justice leadership",
            "2024 national-legislator historical cohort",
        ],
        "previous_committed_health":load_json(ROOT/"reports/refresh-health.json"),
    }

def run_stage(name, cmd, limit, env):
    try:
        cp=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,timeout=limit,errors="replace")
        text=(cp.stdout or "")+"\n"+(cp.stderr or "")
        return {"stage":name,"rc":cp.returncode,"status":"OK" if cp.returncode==0 else "EXIT_"+str(cp.returncode),
                "tail":text[-1500:]}
    except subprocess.TimeoutExpired as e:
        return {"stage":name,"rc":124,"status":"TIMEOUT","tail":str(e)[-400:]}
    except OSError as e:
        return {"stage":name,"rc":125,"status":"EXEC_ERROR","tail":str(e)[-400:]}

def audit_source(source):
    s=next(x for x in SOURCES if x.key==source)
    rawpath=ROOT/f"data/raw/{source}_expense.json"
    prior=load_json(rawpath)
    prior_rows=prior.get("rows") or []
    prior_files=prior.get("files") or []
    prior_byid={str(r.get("row_id")):r for r in prior_rows}
    env=os.environ.copy()
    env["PYTHONPATH"]=str(ROOT/"pipeline")
    stage_specs=[
        ("DISCOVERY",[sys.executable,"pipeline/capital_backfill.py","--since","2024-12","--until","2026-10","--source",source],170),
        ("DISCOVERY_GUARD",[sys.executable,"pipeline/guard_full_council.py","--source",source,"--phase","discovery","--baseline-ref","HEAD"],40),
        ("INGEST",[sys.executable,"pipeline/ingest_council_expense.py","--source",source,"--incremental"],170),
        ("DATE_REPAIR",[sys.executable,"pipeline/repair_raw_dates.py","--source",source,"--min-valid","0.0","--preserve-baseline-ref","HEAD"],50),
        ("INTEGRITY_GUARD",[sys.executable,"pipeline/guard_full_council.py","--source",source,"--phase","integrity","--baseline-ref","HEAD"],40),
        ("STRICT_QA",[sys.executable,"pipeline/qa_council_publication.py","--source",source,"--baseline-ref","HEAD"],60),
        ("CANDIDATE",[sys.executable,"pipeline/build_source_candidates.py","--source",source,"--top","100"],50),
    ]
    record={"source":source,"institution":s.institution,"region":s.region,
            "baseline_rows":len(prior_rows),"baseline_files":len(prior_files),
            "baseline_available":bool(prior_rows),"stages":[]}
    for stage,cmd,timeout in stage_specs:
        check=run_stage(stage,cmd,timeout,env)
        record["stages"].append(check)
        if stage=="DISCOVERY" and check["rc"]==0:
            d=load_json(ROOT/f"reports/capital-backfill-discovery-{source}.json")
            posts=[x for x in d.get("posts",[]) if x.get("source")==source and x.get("post_url")]
            record["discovery"]={
                "posts":len(posts),
                "attachments":sum(len(x.get("attachments") or []) for x in posts),
                "problem_posts":sum(bool(x.get("error")) for x in d.get("posts",[]) if x.get("source")==source),
                "sample_errors":[x.get("error") for x in d.get("posts",[]) if x.get("source")==source and x.get("error")][:5]
            }
        if stage=="INGEST" and check["rc"]==0:
            d=load_json(rawpath)
            record["ingestion"]={"rows":len(d.get("rows") or []),"files":len(d.get("files") or []),
                                 "errors":len(d.get("errors") or []),"sample_errors":(d.get("errors") or [])[:3]}
        if stage=="STRICT_QA" and check["rc"] in (0,2,3):
            # JSON is printed as a multiline trailing object by the official QA CLI.
            tail=check["tail"]
            if check["rc"]==2:
                m=re.search(r'"failures"\s*:\s*(\[[^\]]*\])',tail,re.S)
                record["qa_failures"]=json.loads(m.group(1)) if m else ["unparsed_strict_qa_failure"]
            if check["rc"]==3:
                record["status"]="NO_CHANGE"
                break
        if check["rc"] != 0:
            record["failed_stage"]=stage
            record["status"]="STALE_OK:"+stage if prior_rows else stage+"_FAILED"
            break
    else:
        record["status"]="UPDATED"
    current=load_json(rawpath)
    cur_rows=current.get("rows") or []
    current_ids={str(r.get("row_id")):r for r in cur_rows}
    lost=set(prior_byid)-set(current_ids)
    changed=[i for i in set(prior_byid)&set(current_ids) if prior_byid[i]!=current_ids[i]]
    duplicate=len(current_ids)!=len(cur_rows)
    record["in_memory_after_rows"]=len(cur_rows)
    record["lost_prior_rows_count"]=len(lost)
    record["changed_prior_rows_count"]=len(changed)
    record["duplicate_row_ids"]=duplicate
    if lost or changed or duplicate:
        record["status"]="STALE_OK:DATA_INTEGRITY" if prior_rows else "DATA_INTEGRITY_FAILED"
        record["failed_stage"]="DATA_INTEGRITY"
        record["data_integrity_examples"]={"lost":sorted(lost)[:5],"changed":changed[:5]}
    return record

def audit_group(n,groups):
    keys=workflow_source_keys()
    if set(keys)!={s.key for s in SOURCES}:raise RuntimeError("source inventory mismatch")
    ordered=[key for index,key in enumerate(keys) if index%groups==n]
    output=[]
    for key in ordered:
        print("START",key,flush=True)
        entry=audit_source(key)
        print("RESULT",key,entry["status"],"baseline",entry["baseline_rows"],
              "after",entry["in_memory_after_rows"],"failure",entry.get("failed_stage",""),flush=True)
        output.append(entry)
    REPORTS.mkdir(parents=True,exist_ok=True)
    path=REPORTS/f"january-2027-council-probe-group-{n}.json"
    report={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"group":n,
            "scope":"40 full-mode council adapters, live evidence at 2026-10-31 only",
            "results":output}
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"group":n,"statuses":dict(Counter(x["status"].split(":")[0] for x in output)),
                      "path":str(path)},ensure_ascii=False))

def summary(path):
    inventory=load_json(path/"january-2027-inventory.json")
    paths=sorted(path.glob("january-2027-council-probe-group-*.json"))
    records=[r for p in paths for r in load_json(p).get("results",[])]
    keys=workflow_source_keys()
    missing=sorted(set(keys)-{r["source"] for r in records})
    dup=[s for s,c in Counter(r["source"] for r in records).items() if c!=1]
    counts=dict(Counter(r["status"] for r in records))
    stage_counts=dict(Counter(r.get("failed_stage") for r in records if r.get("failed_stage")))
    report={"generated_at_utc":datetime.now(timezone.utc).isoformat(),
            "target":"2027-01-15 full refresh, December 2026 disclosures not yet observable",
            "registered_institutions":inventory.get("registered_institutions"),
            "verified_sources_without_adapter":inventory.get("registered_verified_without_full_adapter",[]),
            "tested_sources":len(records),"expected_sources":len(keys),
            "missing":missing,"duplicate_sources":dup,
            "counts":counts,"failure_stages":stage_counts,"sources":sorted(records,key=lambda r:r["source"]),
            "supplemental_registry":inventory.get("supplemental_registry",[])}
    report["preflight_class"]=("INCOMPLETE" if missing or dup else
                              "DEGRADED" if any(r["status"] not in ("UPDATED","NO_CHANGE") for r in records) else "PASS")
    out=path/"january-2027-readiness-summary.json"
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# 2027-01-15 monthly Full Refresh operational readiness","",
           f"- Observed at: {report['generated_at_utc']}",
           "- Evidence observed at 2026-10-31; December 2026 data is not yet published.",
           f"- Full-mode council adapters checked: {len(records)}/{len(keys)}",
           f"- Current result: {report['preflight_class']}",
           f"- Source status counts: {json.dumps(counts,ensure_ascii=False)}","",
           "| Source | Baseline rows | Discovery posts/files | Live simulation | Root failure stage |",
           "|---|---:|---:|---|---|"]
    for r in report["sources"]:
        d=r.get("discovery",{})
        reason=r.get("qa_failures") or r.get("failed_stage") or ""
        lines.append(f"| {r['institution']} ({r['source']}) | {r['baseline_rows']} | "
                     f"{d.get('posts','-')}/{d.get('attachments','-')} | "
                     f"{r['status']} | {str(reason).replace('|','/')[:110]} |")
    lines+=["","## Coverage missing despite verified registry URL",""]
    for x in report["verified_sources_without_adapter"]:
        lines.append(f"- {x.get('institution')}: {x.get('adapter')}")
    lines+=["","## Important boundaries","",
            "- This is an isolated 2026-10-31 live simulation of the January *full-mode* council stages, including P0 guards.",
            "- A successful discovery does not imply a December 2026 official release exists yet.",
            "- All runner edits are discarded; no production main/Pages deployment is performed."]
    md=path/"january-2027-readiness-summary.md"
    md.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="sources"},ensure_ascii=False,indent=2))
    print("markdown",md)
    if missing or dup:raise SystemExit(2)

def main():
    ap=argparse.ArgumentParser()
    cmd=ap.add_subparsers(dest="mode",required=True)
    inv=cmd.add_parser("inventory")
    inv.add_argument("--out",default="reports/january-2027-inventory.json")
    audit=cmd.add_parser("group")
    audit.add_argument("--group",type=int,required=True)
    audit.add_argument("--groups",type=int,default=8)
    summ=cmd.add_parser("summarize")
    summ.add_argument("--path",type=Path,default=REPORTS)
    args=ap.parse_args()
    if args.mode=="inventory":
        report=registry_inventory()
        p=ROOT/args.out
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({k:v for k,v in report.items() if k not in ("sources","previous_committed_health")},ensure_ascii=False,indent=2))
    elif args.mode=="group":
        audit_group(args.group,args.groups)
    else:summary(args.path)

if __name__=="__main__":main()
