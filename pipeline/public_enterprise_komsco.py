#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from public_enterprise_discovery import decode, extract_year_month, looks_file, parse_links

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="komsco"
INSTITUTION="한국조폐공사"
LISTING="https://www.komsco.com/kor/article/ATCL7e0c1d65f"
BROWSER_UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"


def fetch(url:str)->str:
    req=urllib.request.Request(url,headers={
        "User-Agent":BROWSER_UA,
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language":"ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
        "Referer":"https://www.komsco.com/kor",
    })
    with urllib.request.urlopen(req,timeout=35) as r:
        return decode(r.read(),r.headers.get_content_charset())


def discover(year:int)->dict:
    years={year,year-1}
    out={"key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership","default_role":"임원","years":sorted(years),"pages":[],"attachments":[],"errors":[]}
    listing_urls=[LISTING]+[LISTING+f"?pageIndex={p}" for p in range(2,8)]
    docs=[]
    with ThreadPoolExecutor(max_workers=min(8,len(listing_urls))) as pool:
        fm={pool.submit(fetch,u):u for u in listing_urls}
        for fut in as_completed(fm):
            u=fm[fut]
            try: docs.append((u,fut.result()));out["pages"].append(u)
            except Exception as e: out["errors"].append(f"listing {u}: {type(e).__name__}: {e}")

    if not docs:
        out["diagnostics"]=[]
    else:
        diagnostic_doc=docs[0][1]
        snippets=[]
        for pattern in (r"업무추진비", r"onclick", r"download", r"article"):
            for match in re.finditer(pattern, diagnostic_doc, re.I):
                start=max(0,match.start()-240);end=min(len(diagnostic_doc),match.end()+420)
                snippet=" ".join(diagnostic_doc[start:end].split())
                if snippet not in snippets:
                    snippets.append(snippet)
                if len(snippets)>=16:
                    break
            if len(snippets)>=16:
                break
        out["diagnostics"]=snippets

    details=[];seen=set()
    for base,doc in docs:
        for x in parse_links(base,doc):
            label=" ".join((x.get("text","")+" "+x.get("url","")).split())
            if not any(str(y) in label for y in years): continue
            if looks_file(x):
                if x["url"] in seen: continue
                seen.add(x["url"]);y,m=extract_year_month(label)
                out["attachments"].append({**x,"year":y,"month":m,"parent":base})
            elif "업무추진비" in label and x["url"] not in seen:
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
                y,m=extract_year_month(label)
                if y not in years:continue
                if a["url"] in seen:continue
                seen.add(a["url"])
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
    print(json.dumps({"key":KEY,"status":fresh["status"],"pages":len(fresh["pages"]),"attachments":len(fresh["attachments"]),"errors":fresh["errors"][:5],"diagnostics":fresh.get("diagnostics",[])[:12]},ensure_ascii=False))

if __name__=="__main__":main()
