#!/usr/bin/env python3
from __future__ import annotations

import html, json, re, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="kicece"
INSTITUTION="한국영유아보육·교육진흥원"
LISTING="https://www.kicece.or.kr/kcpi/openmag/bzexpense.do"
DETAIL="https://www.kicece.or.kr/kcpi/openmag/bzexpenseDetail.do?year={ym}"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        t=tag.lower()
        if t=="tr": self.row=[]
        elif t in ("td","th") and self.row is not None: self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        t=tag.lower()
        if t in ("td","th") and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split())); self.cell=None
        elif t=="tr" and self.row is not None:
            if self.row:self.rows.append(self.row)
            self.row=None

def fetch(url:str)->str:
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req,timeout=20) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8","replace")

def to_int(v):
    s=re.sub(r"[^0-9.-]","",str(v or ""))
    try:return int(round(float(s)))
    except Exception:return None

def parse_month(year:int,month:int):
    ym=f"{year:04d}{month:02d}";url=DETAIL.format(ym=ym)
    try:doc=fetch(url)
    except Exception as e:return [],url,f"{type(e).__name__}: {e}"
    p=TableParser();p.feed(doc);rows=[]
    for i,cells in enumerate(p.rows,1):
        if len(cells)<7:continue
        date=cells[0].strip()
        if not re.fullmatch(rf"{year}-0?{month}-\d{{1,2}}",date):continue
        merchant=cells[2].strip()
        if not merchant or merchant in {"-","사용처(장소)"}:continue
        rows.append({
            "source_key":KEY,"institution":INSTITUTION,
            "cohort":"public_enterprise_leadership",
            "role":"기관장","department":"",
            "used_date":datetime.strptime(date,"%Y-%m-%d").date().isoformat(),
            "used_time":"",
            "merchant":merchant,"address":"",
            "purpose":cells[1].strip(),
            "target":cells[3].strip(),
            "payment_method":cells[4].strip(),
            "people":to_int(cells[5]),"amount":to_int(cells[6]),
            "source_amount_scale":1,"source_category":"기관장",
            "source_url":url,"source_sheet":f"{year}-{month:02d}",
            "source_row":i,
            "row_id":f"kicece:{ym}:{i}",
        })
    return rows,url,None

def discover(year:int)->dict:
    years=[year-1,year];jobs=[]
    now=datetime.now()
    for y in years:
        end=12 if y<year else min(12,now.month)
        for m in range(1,end+1):jobs.append((y,m))
    rows=[];pages=[LISTING];errors=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        fm={pool.submit(parse_month,y,m):(y,m) for y,m in jobs}
        for fut in as_completed(fm):
            parsed,url,err=fut.result();pages.append(url)
            rows.extend(parsed)
            if err:errors.append(f"{url}: {err}")
    rows.sort(key=lambda r:(r["used_date"],r["row_id"]))
    return {
        "key":KEY,"institution":INSTITUTION,
        "cohort":"public_enterprise_leadership",
        "default_role":"기관장","years":years,
        "pages":list(dict.fromkeys(pages)),
        "attachments":[],"inline_rows":rows,"inline_replace":True,
        "errors":errors,"parseable_attachments":0,
        "status":"PARSEABLE_FOUND" if rows else ("FETCH_FAILED" if errors else "NO_FILES_FOUND"),
    }

def main():
    payload=json.loads(REPORT.read_text(encoding="utf-8"))
    fresh=discover(int(payload.get("year") or datetime.now().year))
    payload["sources"]=[x for x in payload.get("sources",[]) if x.get("key")!=KEY]+[fresh]
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
        "key":KEY,"status":fresh["status"],"rows":len(fresh["inline_rows"]),
        "merchants":len({r["merchant"] for r in fresh["inline_rows"]}),
        "date_min":min((r["used_date"] for r in fresh["inline_rows"]),default=""),
        "date_max":max((r["used_date"] for r in fresh["inline_rows"]),default=""),
        "errors":fresh["errors"][:8],
    },ensure_ascii=False))

if __name__=="__main__":main()
