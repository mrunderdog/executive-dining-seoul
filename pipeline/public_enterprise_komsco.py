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
OFFICIAL="https://www.komsco.com/kor/article/ATCL7e0c1d65f"
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
        "key":KEY,
        "institution":INSTITUTION,
        "cohort":"public_enterprise_leadership",
        "default_role":"기관장",
        "years":sorted(years),
        "pages":[ALIO,OFFICIAL],
        "attachments":[],
        "errors":[],
        "status":"TRACK_ONLY",
        "parseable_attachments":0,
        "source_mode":"alio_aggregate_only",
        "format_hint":"xlsx-aggregate-only",
        "note":"KOMSCO 공식 홈페이지의 임원 업무추진비 메뉴는 확인되지만 GitHub runner 등 무인 수집 환경에는 차단 페이지를 반환한다. ALIO 기관장 업무추진비(C0257/20701)는 공식 XLSX로 접근 가능하나 월별 집행내역·건수·금액만 공개되어 merchant/사용처가 없으므로 지도 데이터로 출판하지 않는다.",
        "aggregate_files":[]
    }
    try:
        doc=fetch(ALIO)
    except Exception as e:
        out["errors"].append(f"ALIO {ALIO}: {type(e).__name__}: {e}")
        return out

    dm=re.search(r'disclosureNo\s*:\s*"([^"]+)"',doc) or re.search(r'\$submissionNo\s*=\s*"?([0-9]+)',doc)
    if not dm:
        out["errors"].append("ALIO disclosureNo missing")
        return out

    disclosure=dm.group(1)
    for fm in re.finditer(r'<option\s+value="([^"]+)">\s*([^<]+\.(?:xlsx?|xls))\s*</option>',doc,re.I):
        file_no,label=fm.group(1),html.unescape(fm.group(2)).strip()
        ym=re.search(r'(20\d{2})',label)
        if not ym or int(ym.group(1)) not in years:
            continue
        out["aggregate_files"].append({
            "text":label,
            "url":f"https://www.alio.go.kr/download/file.json?d={disclosure}&f={file_no}",
            "year":int(ym.group(1)),
            "parent":ALIO,
        })
    return out


def main():
    payload=json.loads(REPORT.read_text(encoding="utf-8"))
    fresh=discover(int(payload.get("year") or datetime.now().year))
    payload["sources"]=[x for x in payload.get("sources",[]) if x.get("key")!=KEY]+[fresh]
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
        "key":KEY,
        "status":fresh["status"],
        "aggregate_files":len(fresh.get("aggregate_files",[])),
        "errors":fresh["errors"][:5]
    },ensure_ascii=False))


if __name__=="__main__":
    main()
