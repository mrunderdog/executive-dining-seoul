#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from central_executive_discovery import fetch, parse_links, looks_file, extract_year_month, discover_source as discover_central_source

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"sources"/"justice_leadership_registry.json"
REPORTS=ROOT/"reports"
CENTRAL_REGISTRY=ROOT/"sources"/"central_executive_registry.json"
PARSEABLE_EXTS=(".xlsx",".xls",".csv",".hwpx",".pdf")


def txt(v): return " ".join(str(v or "").split()).strip()


def source_match(src:dict,label:str)->bool:
    s=txt(label)
    includes=[txt(x) for x in src.get("include_terms",[]) if txt(x)]
    excludes=[txt(x) for x in src.get("exclude_terms",[]) if txt(x)]
    if any(x in s for x in excludes):
        return False
    return all(x in s for x in includes) if includes else ("업무추진비" in s)


def same_host(a:str,b:str)->bool:
    return urllib.parse.urlsplit(a).netloc==urllib.parse.urlsplit(b).netloc


def discover(src:dict,year:int)->dict:
    out={
        "key":src["key"],"institution":src["institution"],"verified":bool(src.get("verified")),
        "default_role":src.get("default_role",""),"source_type":src.get("source_type","official_routine"),
        "merchant_expectation":src.get("merchant_expectation","unknown"),"format_hint":src.get("format_hint",""),
        "pages":[],"attachments":[],"errors":[]
    }
    if not src.get("verified"):
        out["status"]="DISCOVERY_REQUIRED"
        out["parseable_attachments"]=0
        return out
    if src.get("adapter_required"):
        out["status"]="ADAPTER_REQUIRED"
        out["parseable_attachments"]=0
        return out
    q=deque((u,0,"") for u in (src.get("listing_urls") or []))
    seen_pages=set(); seen_files=set(); max_pages=int(src.get("max_pages") or 60)
    while q and len(seen_pages)<max_pages:
        url,depth,parent_label=q.popleft()
        if url in seen_pages: continue
        seen_pages.add(url); out["pages"].append(url)
        try:
            doc=fetch(url)
        except Exception as e:
            out["errors"].append(f"{url}: {type(e).__name__}: {e}")
            continue
        for link in parse_links(url,doc):
            label=txt(parent_label+" "+link.get("text",""))
            target=link.get("url") or ""
            if not target: continue
            if looks_file(link):
                if not source_match(src,label+" "+target):
                    continue
                if target in seen_files: continue
                seen_files.add(target)
                y,m=extract_year_month(label)
                if y and y not in {year,year-1}: continue
                out["attachments"].append({
                    "text":label or link.get("text",""),"url":target,"year":y,"month":m,
                    "parent":url
                })
                continue
            if depth>=2 or not same_host(url,target):
                continue
            probe=label+" "+target
            # Follow only expense/detail/list routes to avoid crawling the whole institution.
            if ("업무추진비" in probe
                    or "/bbs/" in target.lower() or "/board/" in target.lower()):
                q.append((target,depth+1,label))
    out["parseable_attachments"]=sum(
        any(ext in (a.get("text","")+" "+a.get("url","")).lower() for ext in PARSEABLE_EXTS)
        and "synapview" not in a.get("url","").lower()
        for a in out["attachments"]
    )
    out["status"]=(
        "PARSEABLE_FOUND" if out["parseable_attachments"] else
        "FILES_FOUND_UNSUPPORTED" if out["attachments"] else
        "FETCH_FAILED" if out["errors"] else "NO_FILES_FOUND"
    )
    return out


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--year",type=int,default=datetime.now().year); args=ap.parse_args()
    reg=json.loads(REGISTRY.read_text(encoding="utf-8"))
    direct_sources=reg.get("sources",[])
    rows=[]
    with ThreadPoolExecutor(max_workers=min(8,max(1,len(direct_sources)))) as pool:
        futures={pool.submit(discover,src,args.year):src for src in direct_sources}
        for fut in as_completed(futures):
            src=futures[fut]
            try:
                rows.append(fut.result())
            except Exception as e:
                rows.append({
                    "key":src.get("key"),"institution":src.get("institution"),"verified":bool(src.get("verified")),
                    "default_role":src.get("default_role",""),"source_type":src.get("source_type","official_routine"),
                    "merchant_expectation":src.get("merchant_expectation","unknown"),"format_hint":src.get("format_hint",""),
                    "pages":[],"attachments":[],"errors":[f"worker {type(e).__name__}: {e}"],
                    "parseable_attachments":0,"status":"FETCH_FAILED"
                })
    order={x.get("key"):i for i,x in enumerate(direct_sources)}
    rows.sort(key=lambda x:order.get(x.get("key"),999))
    # Refresh the two legal-administration sources directly so this pipeline is
    # independent from the broader central-government refresh cadence.
    inherited=[]
    central_reg=json.loads(CENTRAL_REGISTRY.read_text(encoding="utf-8"))
    central_by_key={x.get("key"):x for x in central_reg.get("sources",[])}
    inherited_cfg=reg.get("inherited_central_sources",[])
    def run_inherited(item):
        base=central_by_key.get(item.get("source_key"))
        if not base:
            return {
                "key":item.get("source_key"),"institution":item.get("institution"),
                "default_role":"","source_type":item.get("source_type","official_routine"),
                "inherited_from":"central_executive","role_scope":item.get("role_scope",""),
                "attachments":[],"parseable_attachments":0,"status":"CENTRAL_REGISTRY_MISSING","errors":[]
            }
        src=discover_central_source(base,args.year)
        return {
            **src,
            "default_role":"",
            "source_type":item.get("source_type","official_routine"),
            "inherited_from":"central_executive",
            "role_scope":item.get("role_scope",""),
        }
    with ThreadPoolExecutor(max_workers=max(1,len(inherited_cfg))) as pool:
        futures={pool.submit(run_inherited,item):item for item in inherited_cfg}
        for fut in as_completed(futures):
            item=futures[fut]
            try:
                inherited.append(fut.result())
            except Exception as e:
                inherited.append({
                    "key":item.get("source_key"),"institution":item.get("institution"),
                    "default_role":"","source_type":item.get("source_type","official_routine"),
                    "inherited_from":"central_executive","role_scope":item.get("role_scope",""),
                    "attachments":[],"parseable_attachments":0,"status":"FETCH_FAILED",
                    "errors":[f"worker {type(e).__name__}: {e}"]
                })
    inherited_order={x.get("source_key"):i for i,x in enumerate(inherited_cfg)}
    inherited.sort(key=lambda x:inherited_order.get(x.get("key"),999))
    payload={"generated_at":datetime.now().isoformat(timespec="seconds"),"year":args.year,
             "cohort":"justice_leadership","inherited_sources":inherited,"sources":rows}
    REPORTS.mkdir(exist_ok=True)
    (REPORTS/"justice-leadership-discovery.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    md=[f"# Justice leadership source discovery — {args.year}","",
        "| Institution | Source | Status | Files | Parseable | Merchant expectation |",
        "|---|---|---|---:|---:|---|"]
    for r in inherited:
        md.append(f"| {r['institution']} | inherited | {r['status']} | {len(r.get('attachments',[]))} | {r.get('parseable_attachments',0)} | merchant-level |")
    for r in rows:
        md.append(f"| {r['institution']} | direct | {r['status']} | {len(r.get('attachments',[]))} | {r.get('parseable_attachments',0)} | {r.get('merchant_expectation','unknown')} |")
    (REPORTS/"justice-leadership-discovery.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"inherited":len(inherited),"direct":len(rows),
                      "parseable_sources":sum(x.get("parseable_attachments",0)>0 for x in inherited+rows),
                      "files":sum(len(x.get("attachments",[])) for x in inherited+rows)},ensure_ascii=False))


if __name__=="__main__": main()
