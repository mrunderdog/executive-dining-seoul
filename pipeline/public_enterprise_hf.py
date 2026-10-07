#!/usr/bin/env python3
from __future__ import annotations

import html, io, json, re, urllib.parse, urllib.request, zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="hf"
INSTITUTION="한국주택금융공사"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
SOURCES=[
    ("기관장","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_01.do"),
    ("감사","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_02.do"),
    ("임원","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_03.do"),
]
NS={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}

class AParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.items=[]; self.cur=None
    def handle_starttag(self,tag,attrs):
        if tag.lower()=="a":
            d=dict(attrs); self.cur={"href":d.get("href",""),"text":[]}
    def handle_data(self,data):
        if self.cur is not None: self.cur["text"].append(data)
    def handle_endtag(self,tag):
        if tag.lower()=="a" and self.cur is not None:
            self.cur["text"]=" ".join(" ".join(self.cur["text"]).split())
            self.items.append(self.cur); self.cur=None

def fetch(url:str,binary:bool=False,referer:str=""):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Referer":referer or url})
    with urllib.request.urlopen(req,timeout=15) as r:
        raw=r.read()
        return raw if binary else raw.decode(r.headers.get_content_charset() or "utf-8","replace")

def anchors(base:str,doc:str):
    p=AParser(); p.feed(doc)
    return [{"text":x["text"],"url":urllib.parse.urljoin(base,html.unescape(x["href"]))} for x in p.items]

def excel_date(value:str)->str:
    s=str(value or "").strip()
    try:
        n=float(s)
        if 30000<=n<=60000:
            return (datetime(1899,12,30)+timedelta(days=n)).date().isoformat()
    except Exception:
        pass
    m=re.search(r"(20\d{2})[-./년\s]+(\d{1,2})[-./월\s]+(\d{1,2})",s)
    if not m:return ""
    try:return datetime(*map(int,m.groups())).date().isoformat()
    except ValueError:return ""

def col(ref:str)->str:
    m=re.match(r"([A-Z]+)",ref or "")
    return m.group(1) if m else ""

def sheets(blob:bytes):
    z=zipfile.ZipFile(io.BytesIO(blob)); shared=[]
    if "xl/sharedStrings.xml" in z.namelist():
        root=ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("a:si",NS):
            shared.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
    wb=ET.fromstring(z.read("xl/workbook.xml"))
    rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap={r.attrib["Id"]:r.attrib["Target"] for r in rels}
    for sh in wb.find("a:sheets",NS):
        rid=sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id","")
        target=relmap.get(rid,"")
        path=target if target.startswith("xl/") else "xl/"+target.lstrip("/")
        if path not in z.namelist():path="xl/"+target.replace("../","").lstrip("/")
        if path not in z.namelist():continue
        root=ET.fromstring(z.read(path)); rows=[]
        for row in root.findall(".//a:sheetData/a:row",NS):
            vals={}
            for c in row.findall("a:c",NS):
                typ=c.attrib.get("t",""); v=c.find("a:v",NS); val="" if v is None else (v.text or "")
                if typ=="s" and val.isdigit() and int(val)<len(shared):val=shared[int(val)]
                elif typ=="inlineStr":val="".join(t.text or "" for t in c.iter() if t.tag.endswith("}t"))
                vals[col(c.attrib.get("r",""))]=str(val).strip()
            rows.append((int(row.attrib.get("r","0") or 0),vals))
        yield sh.attrib.get("name",""),rows

def role_from_user(text:str)->str:
    text=" ".join(str(text or "").split())
    m=re.match(r"(?:상임)?(?:부)?(?:사장|감사|이사|전무|상무|본부장)",text)
    return m.group(0) if m else "임원"

def parse_file(job:dict):
    try:blob=fetch(job["url"],True,job["parent"])
    except Exception as e:return [],f"download {job['url']}: {type(e).__name__}: {e}"
    out=[]
    for sheet,rows in sheets(blob):
        header=None; layout=None
        for ri,v in rows:
            vals={k:" ".join(str(x).split()) for k,x in v.items()}
            if vals.get("A")=="사용일자" and "사용처" in (vals.get("C","")+vals.get("D","")):
                if vals.get("B")=="사용자":
                    layout={"date":"A","user":"B","purpose":"C","merchant":"D","target":"E","method":"F","people":"G","amount":"H"}
                else:
                    layout={"date":"A","purpose":"B","merchant":"C","target":"D","method":"E","people":"F","amount":"G"}
                header=ri; continue
            if not layout or ri<=header:continue
            date=excel_date(vals.get(layout["date"],""))
            merchant=vals.get(layout["merchant"],"")
            purpose=vals.get(layout["purpose"],"")
            if not date or not merchant or merchant in {"사용처(장소)","계"}:continue
            role=job["role"]
            if layout.get("user"):role=role_from_user(vals.get(layout["user"],""))
            def num(key,scale=1):
                try:return int(round(float(vals.get(layout[key],"").replace(",",""))*scale))
                except Exception:return None
            out.append({
                "source_key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
                "role":role,"department":"","used_date":date,"used_time":"",
                "merchant":merchant,"address":"","purpose":purpose,
                "people":num("people"),"amount":num("amount"),
                "source_amount_scale":1,"payment_method":vals.get(layout["method"],""),
                "source_category":job["role"],"source_url":job["url"],
                "source_sheet":sheet,"source_row":ri,"target":vals.get(layout["target"],""),
                "row_id":f"hf:{job['article_no']}:{job['attach_no']}:{sheet}:{ri}",
            })
    return out,None

def discover(year:int)->dict:
    years={year,year-1}; pages=[]; jobs=[]; errors=[]
    for role,base in SOURCES:
        for offset in (0,10,20):
            listing=base+(f"?article.offset={offset}&articleLimit=10" if offset else "")
            try:doc=fetch(listing)
            except Exception as e:
                errors.append(f"listing {listing}: {type(e).__name__}: {e}");continue
            pages.append(listing)
            for a in anchors(listing,doc):
                ym=re.search(r"(20\d{2})년도\s*(\d{1,2})월\s*업무추진비",a["text"])
                am=re.search(r"articleNo=(\d+)",a["url"])
                if not ym or not am or int(ym.group(1)) not in years:continue
                detail=a["url"]
                try:ddoc=fetch(detail)
                except Exception as e:
                    errors.append(f"detail {detail}: {type(e).__name__}: {e}");continue
                pages.append(detail)
                for fa in anchors(detail,ddoc):
                    if not re.search(r"\.xlsx?$",fa["text"],re.I):continue
                    nm=re.search(r"attachNo=(\d+)",fa["url"])
                    if not nm:continue
                    jobs.append({"role":role,"url":fa["url"],"parent":detail,"article_no":am.group(1),"attach_no":nm.group(1),"year":int(ym.group(1)),"month":int(ym.group(2)),"text":fa["text"]})
                    break
    uniq={(j["article_no"],j["attach_no"]):j for j in jobs}
    jobs=list(uniq.values()); rows=[]
    if jobs:
        with ThreadPoolExecutor(max_workers=min(8,len(jobs))) as pool:
            fm={pool.submit(parse_file,j):j for j in jobs}
            for fut in as_completed(fm):
                parsed,err=fut.result(); rows.extend(parsed)
                if err:errors.append(err)
    rows.sort(key=lambda r:(r["used_date"],r["role"],r["row_id"]))
    return {
        "key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
        "default_role":"기관장·감사·임원","years":sorted(years),
        "pages":list(dict.fromkeys(pages)),
        "attachments":[{"text":j["text"],"url":j["url"],"download_url":j["url"],"year":j["year"],"month":j["month"],"parent":j["parent"],"attachment_id":f"{j['article_no']}|{j['attach_no']}"} for j in jobs],
        "inline_rows":rows,"inline_replace":True,"errors":errors,
        "parseable_attachments":len(jobs),
        "status":"PARSEABLE_FOUND" if rows else ("FETCH_FAILED" if errors else "NO_FILES_FOUND"),
    }

def main():
    payload=json.loads(REPORT.read_text(encoding="utf-8"))
    fresh=discover(int(payload.get("year") or datetime.now().year))
    payload["sources"]=[x for x in payload.get("sources",[]) if x.get("key")!=KEY]+[fresh]
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"key":KEY,"status":fresh["status"],"attachments":len(fresh["attachments"]),"rows":len(fresh["inline_rows"]),"merchants":len({r["merchant"] for r in fresh["inline_rows"]}),"roles":sorted({r["role"] for r in fresh["inline_rows"]}),"errors":fresh["errors"][:8]},ensure_ascii=False))

if __name__=="__main__":main()
