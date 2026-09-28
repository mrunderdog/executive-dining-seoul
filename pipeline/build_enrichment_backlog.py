#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, math
from pathlib import Path

from data_io import load_payload
from published_sources import merge_published_sources
from extra_published import merge_extra_published
from global_entities import merge_global_entities
from coordinate_selection import safe_geocoder_address
from build_site import load_geo_cache

ROOT=Path(__file__).resolve().parents[1]

def t(v): return " ".join(str(v or "").split()).strip()

def signal(r):
    return max(float((r.get("executive") or {}).get("score") or 0), float((r.get("destination") or {}).get("score") or 0))

def priority(r):
    b=r.get("business") or {}
    e=r.get("evidence") or {}
    x=r.get("cross_institution") or {}
    missing_address=not t(r.get("address"))
    missing_cat=(not t(b.get("category"))) or ("확인 필요" in t(b.get("category")))
    missing_phone=not t(b.get("phone"))
    missing_url=not t(b.get("url"))
    gaps=40*missing_address+10*missing_cat+5*missing_phone+4*missing_url
    visits=min(int(e.get("visits") or 0),50)
    institutions=min(int(x.get("institution_count") or len(r.get("institutions") or [])),5)
    return round(gaps+signal(r)*.65+visits*1.5+institutions*9,1)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default=str(ROOT/"reports"/"enrichment-backlog.json"))
    ap.add_argument("--limit",type=int,default=150)
    args=ap.parse_args()

    payload=merge_global_entities(merge_extra_published(merge_published_sources(load_payload())))
    rows=payload.get("records") or []
    geo=load_geo_cache()
    backfilled=0
    for r in rows:
        if not t(r.get("address")):
            addr,key=safe_geocoder_address(r,geo)
            if addr:
                r["address"]=addr
                r["address_enrichment_source"]="nominatim_exact_name"
                r["address_enrichment_key"]=key
                backfilled+=1

    out=[]
    for r in rows:
        b=r.get("business") or {}
        missing={
            "address":not t(r.get("address")),
            "category":(not t(b.get("category"))) or ("확인 필요" in t(b.get("category"))),
            "phone":not t(b.get("phone")),
            "url":not t(b.get("url")),
        }
        if not any(missing.values()): continue
        out.append({
            "priority":priority(r),
            "name":t(b.get("display")) or t(r.get("name")),
            "raw_name":t(r.get("name")),
            "origin":t(r.get("origin")),
            "jurisdiction":t(r.get("jurisdiction")),
            "institutions":r.get("institutions") or ([r.get("institution")] if r.get("institution") else []),
            "visits":int((r.get("evidence") or {}).get("visits") or 0),
            "signal":signal(r),
            "cross_institutions":int((r.get("cross_institution") or {}).get("institution_count") or 0),
            "missing":missing,
            "address":t(r.get("address")),
            "category":t(b.get("category")),
            "phone":t(b.get("phone")),
            "url":t(b.get("url")),
        })
    out.sort(key=lambda x:(x["missing"]["address"],x["priority"],x["visits"]),reverse=True)
    report={
      "total_records":len(rows),
      "safe_address_backfills":backfilled,
      "missing_address":sum(not t(r.get("address")) for r in rows),
      "missing_category":sum((not t((r.get("business") or {}).get("category"))) or "확인 필요" in t((r.get("business") or {}).get("category")) for r in rows),
      "missing_phone":sum(not t((r.get("business") or {}).get("phone")) for r in rows),
      "missing_url":sum(not t((r.get("business") or {}).get("url")) for r in rows),
      "backlog":out[:args.limit],
    }
    p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))

if __name__=="__main__": main()
