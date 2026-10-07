#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path

from public_enterprise_discovery import decode

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="komsco"
INSTITUTION="한국조폐공사"
ALIO="https://www.alio.go.kr/mobile/item/itemReportTerm.do?apbaId=C0257&disclosureNo=&reportFormRootNo=20701"
BROWSER_UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"


def fetch(url:str)->str:
    req=urllib.request.Request(url,headers={
        "User-Agent":BROWSER_UA,
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language":"ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
        "Referer":"https://www.alio.go.kr/",
    })
    with urllib.request.urlopen(req,timeout=15) as r:
        return decode(r.read(),r.headers.get_content_charset())


def discover(year:int)->dict:
    years={year,year-1}
    out={
        "key":KEY,"institution":INSTITUTION,
        "cohort":"public_enterprise_leadership","default_role":"기관장",
        "years":sorted(years),"pages":[ALIO],"attachments":[],"errors":[],
        "source_mode":"alio_official"
    }
    try:
        doc=fetch(ALIO)
    except Exception as e:
        out["errors"].append(f"ALIO {ALIO}: {type(e).__name__}: {e}")
        out["parseable_attachments"]=0
        out["status"]="FETCH_FAILED"
        return out

    dm=re.search(r'disclosureNo\s*:\s*"([^"]+)"',doc) or re.search(r'\$submissionNo\s*=\s*"?([0-9]+)',doc)
    if not dm:
        out["errors"].append("ALIO disclosureNo missing")
        out["diagnostics"]=[" ".join(doc[:1800].split())]
        out["parseable_attachments"]=0
        out["status"]="NO_FILES_FOUND"
        return out

    disclosure=dm.group(1)
    seen=set()
    labels=[]
    for fm in re.finditer(r'<option\s+value="([^"]+)">\s*([^<]+\.(?:xlsx?|xls))\s*</option>',doc,re.I):
        file_no,label=fm.group(1),html.unescape(fm.group(2)).strip()
        labels.append(label)
        ym=re.search(r'(20\d{2})',label)
        if not ym:
            continue
        y=int(ym.group(1))
        if y not in years:
            continue
        url=f"https://www.alio.go.kr/download/file.json?d={disclosure}&f={file_no}"
        if url in seen:
            continue
        seen.add(url)
        out["attachments"].append({
            "text":label,"url":url,"download_url":url,
            "year":y,"month":None,"parent":ALIO,
            "attachment_id":f"{disclosure}|{file_no}"
        })

    out["diagnostics"]=[f"disclosure={disclosure}",*labels[:20]]
    out["parseable_attachments"]=len(out["attachments"])
    out["status"]="PARSEABLE_FOUND" if out["attachments"] else "NO_FILES_FOUND"
    return out


def main():
    payload=json.loads(REPORT.read_text(encoding="utf-8"))
    fresh=discover(int(payload.get("year") or datetime.now().year))
    payload["sources"]=[x for x in payload.get("sources",[]) if x.get("key")!=KEY]+[fresh]
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
        "key":KEY,"status":fresh["status"],
        "pages":len(fresh["pages"]),"attachments":len(fresh["attachments"]),
        "errors":fresh["errors"][:5],"diagnostics":fresh.get("diagnostics",[])[:20]
    },ensure_ascii=False))


if __name__=="__main__":
    main()
