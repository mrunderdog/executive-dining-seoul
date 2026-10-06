#!/usr/bin/env python3
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from public_enterprise_discovery import extract_year_month, fetch, looks_file, parse_links

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="komsco"
INSTITUTION="한국조폐공사"
SEEDS=[
    "https://www.komsco.com/kor",
    "https://www.komsco.com/kor/article/ATCL77594935c",
]


def discover(year:int)->dict:
    years={year,year-1}
    out={"key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership","default_role":"임원","years":sorted(years),"pages":[],"attachments":[],"errors":[]}
    menu_urls=[]
    for seed in SEEDS:
        try: doc=fetch(seed)
        except Exception as e:
            out["errors"].append(f"seed {seed}: {type(e).__name__}: {e}"); continue
        out["pages"].append(seed)
        for x in parse_links(seed,doc):
            if "임원 업무추진비" in (x.get("text") or ""):
                menu_urls.append(x["url"])
    menu_urls=list(dict.fromkeys(menu_urls))
    if not menu_urls:
        out["status"]="ROUTE_NOT_FOUND";out["parseable_attachments"]=0;return out

    listing_urls=[]
    for menu in menu_urls:
        listing_urls.append(menu)
        for p in range(2,6):
            listing_urls.append(menu+("&" if "?" in menu else "?")+f"pageIndex={p}")
    docs=[]
    with ThreadPoolExecutor(max_workers=min(8,len(listing_urls))) as pool:
        fm={pool.submit(fetch,u):u for u in listing_urls}
        for fut in as_completed(fm):
            u=fm[fut]
            try: docs.append((u,fut.result()));out["pages"].append(u)
            except Exception as e: out["errors"].append(f"listing {u}: {type(e).__name__}: {e}")

    details=[];seen=set()
    for base,doc in docs:
        for x in parse_links(base,doc):
            label=" ".join((x.get("text","")+" "+x.get("url","")).split())
            if "업무추진비" not in label or not any(str(y) in label for y in years): continue
            if looks_file(x):
                if x["url"] in seen: continue
                seen.add(x["url"]);y,m=extract_year_month(label)
                out["attachments"].append({**x,"year":y,"month":m,"parent":base})
            elif x["url"] not in seen:
                seen.add(x["url"]);details.append(x)

    with ThreadPoolExecutor(max_workers=min(8,max(1,len(details)))) as pool:
        fm={pool.submit(fetch,x["url"]):x for x in details}
        for fut in as_completed(fm):
            x=fm[fut];out["pages"].append(x["url"])
            try: doc=fut.result()
            except Exception as e: out["errors"].append(f"detail {x['url']}: {type(e).__name__}: {e}");continue
            for a in parse_links(x["url"],doc):
                if not looks_file(a):continue
                label=" ".join((x.get("text","")+" "+a.get("text","")).split())
                if "업무추진비" not in label or not any(str(y) in label for y in years):continue
                if a["url"] in seen:continue
                seen.add(a["url"]);y,m=extract_year_month(label)
                out["attachments"].append({"text":label,"url":a["url"],"year":y,"month":m,"parent":x["url"]})

    out["pages"]=list(dict.fromkeys(out["pages"]))
    out["parseable_attachments"]=len(out["attachments"])
    out["status"]="PARSEABLE_FOUND" if out["attachments"] else ("FETCH_FAILED" if out["errors"] and not docs else "NO_FILES_FOUND")
    return out


def main():
    payload=json.loads(REPORT.read_text(encoding="utf-8"))
    fresh=discover(int(payload.get("year") or datetime.now().year))
    payload["sources"]=[x for x in payload.get("sources",[]) if x.get("key")!=KEY]+[fresh]
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"key":KEY,"status":fresh["status"],"pages":len(fresh["pages"]),"attachments":len(fresh["attachments"]),"errors":fresh["errors"][:5]},ensure_ascii=False))

if __name__=="__main__":main()
