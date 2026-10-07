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
KEY="hf"; INSTITUTION="한국주택금융공사"
UA="Mozilla/5.0"
ROLE_PAGES=[
 ("기관장","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_01.do"),
 ("감사","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_02.do"),
 ("임원","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_03.do"),
]
NS={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main","r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}

class A(HTMLParser):
    def __init__(self): super().__init__(); self.anchors=[]; self.cur=None
    def handle_starttag(self,t,attrs):
        if t.lower()=="a": self.cur=dict(attrs); self.cur["text"]=[]
    def handle_data(self,d):
        if self.cur is not None:self.cur["text"].append(d)
    def handle_endtag(self,t):
        if t.lower()=="a" and self.cur is not None:
            self.cur["text"]=" ".join(" ".join(self.cur["text"]).split()); self.anchors.append(self.cur); self.cur=None

def fetch(url,referer=""):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Referer":referer or url,"Accept-Language":"ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req,timeout=15) as r:return r.read()

def text_fetch(url,referer=""):
    raw=fetch(url,referer)
    for enc in ("utf-8","cp949","euc-kr"):
        try:return raw.decode(enc)
        except Exception:pass
    return raw.decode("utf-8",errors="replace")

def col(ref):
    m=re.match(r"([A-Z]+)",ref or ""); return m.group(1) if m else ""

def excel_date(v):
    try:
        n=float(v)
        if 30000<=n<=60000:return (datetime(1899,12,30)+timedelta(days=n)).date().isoformat()
    except Exception:pass
    s=" ".join(str(v or "").split()); m=re.search(r"(20\d{2}).*?(\d{1,2}).*?(\d{1,2})",s)
    if not m:return ""
    try:return datetime(int(m.group(1)),int(m.group(2)),int(m.group(3))).date().isoformat()
    except ValueError:return ""

def to_int(v):
    try:return int(round(float(str(v).replace(",",""))))
    except Exception:return None

def xrows(blob):
    z=zipfile.ZipFile(io.BytesIO(blob)); shared=[]
    if "xl/sharedStrings.xml" in z.namelist():
        root=ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("a:si",NS):shared.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
    wb=ET.fromstring(z.read("xl/workbook.xml")); rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap={r.attrib["Id"]:r.attrib["Target"] for r in rels}
    for sh in wb.find("a:sheets",NS):
        sheet=sh.attrib.get("name",""); rid=sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id","")
        target=relmap.get(rid,""); path=target if target.startswith("xl/") else "xl/"+target.lstrip("/")
        if path not in z.namelist():path="xl/"+target.replace("../","").lstrip("/")
        if path not in z.namelist():continue
        root=ET.fromstring(z.read(path))
        for row in root.findall(".//a:sheetData/a:row",NS):
            vals={}
            for c in row.findall("a:c",NS):
                typ=c.attrib.get("t",""); v=c.find("a:v",NS); val="" if v is None else (v.text or "")
                if typ=="s" and val.isdigit() and int(val)<len(shared):val=shared[int(val)]
                elif typ=="inlineStr":val="".join(t.text or "" for t in c.iter() if t.tag.endswith("}t"))
                vals[col(c.attrib.get("r",""))]=" ".join(str(val).split())
            yield sheet,int(row.attrib.get("r","0") or 0),vals

def parse_attachment(att):
    try: blob=fetch(att["url"],att.get("parent",""))
    except Exception as e:return [],f"download {att['url']}: {type(e).__name__}: {e}"
    rows=[]; mode=None; prev_date=""; prev_purpose=""
    for sheet,ri,v in xrows(blob):
        if att["role"]=="임원" and v.get("A")=="사용일자" and v.get("B")=="사용자": mode="exec"; continue
        if att["role"]!="임원" and v.get("A")=="사용일자" and "사용처" in v.get("C",""): mode="fixed"; continue
        if mode=="exec":
            if v.get("A")=="계":continue
            if v.get("A"):prev_date=excel_date(v.get("A")) or prev_date
            role=v.get("B","") or "임원"; purpose=v.get("C","") or prev_purpose
            if v.get("C"):prev_purpose=v.get("C")
            merchant=v.get("D",""); target=v.get("E",""); method=v.get("F",""); people=to_int(v.get("G","")); amount=to_int(v.get("H",""))
        elif mode=="fixed":
            if v.get("A")=="계":continue
            if v.get("A"):prev_date=excel_date(v.get("A")) or prev_date
            role=att["role"]; purpose=v.get("B","") or prev_purpose
            if v.get("B"):prev_purpose=v.get("B")
            merchant=v.get("C",""); target=v.get("D",""); method=v.get("E",""); people=to_int(v.get("F","")); amount=to_int(v.get("G",""))
        else: continue
        if not merchant or not prev_date:continue
        rows.append({"source_key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership","role":" ".join(role.split()),
          "department":"","used_date":prev_date,"used_time":"","merchant":" ".join(merchant.split()),"address":"",
          "purpose":" ".join(purpose.split()),"people":people,"amount":amount,"source_amount_scale":1,
          "payment_method":" ".join(method.split()),"source_category":"","target":" ".join(target.split()),
          "source_url":att["url"],"source_sheet":sheet,"source_row":ri,
          "row_id":f"hf:{att['attachment_id']}:{sheet}:{ri}"})
    return rows,None

def discover(year):
    years={year,year-1}
    out={"key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership","default_role":"기관장·감사·임원",
         "years":sorted(years),"pages":[],"attachments":[],"inline_rows":[],"inline_replace":True,"errors":[]}
    detail_jobs=[]
    for role,listing in ROLE_PAGES:
        for page in range(1,5):
            url=listing if page==1 else listing+f"?pageIndex={page}"
            try:doc=text_fetch(url)
            except Exception as e:out["errors"].append(f"listing {url}: {type(e).__name__}: {e}");continue
            out["pages"].append(url); p=A();p.feed(doc)
            for a in p.anchors:
                txt=a.get("text",""); href=html.unescape(a.get("href","") or "")
                if "업무추진비" not in txt or not any(str(y) in txt for y in years):continue
                if "mode=view" not in href or "articleNo=" not in href:continue
                detail_jobs.append((role,listing,urllib.parse.urljoin(url,href)))
    seen=set();jobs=[]
    for role,listing,detail in detail_jobs:
        if (role,detail) in seen:continue
        seen.add((role,detail));jobs.append((role,listing,detail))
    def fetch_detail(job):
        role,listing,detail=job
        return job,text_fetch(detail,listing)
    if jobs:
        with ThreadPoolExecutor(max_workers=min(8,len(jobs))) as pool:
            fm={pool.submit(fetch_detail,j):j for j in jobs}
            for fut in as_completed(fm):
                role,listing,detail=fm[fut]
                try:
                    _,doc=fut.result()
                except Exception as e:
                    out["errors"].append(f"detail {detail}: {type(e).__name__}: {e}");continue
                out["pages"].append(detail);p=A();p.feed(doc)
                for a in p.anchors:
                    label=a.get("text","");href=html.unescape(a.get("href","") or "")
                    if ".xlsx" not in label.lower():continue
                    ym=re.search(r"(20\d{2})년\s*(\d{1,2})월",label)
                    if not ym:continue
                    y,m=int(ym.group(1)),int(ym.group(2))
                    if y not in years:continue
                    dl=urllib.parse.urljoin(detail,href)
                    out["attachments"].append({"role":role,"text":label,"url":dl,"download_url":dl,"parent":detail,
                        "year":y,"month":m,"attachment_id":urllib.parse.urlsplit(dl).query})
    uniq={a["url"]:a for a in out["attachments"]};out["attachments"]=sorted(uniq.values(),key=lambda a:(a["year"],a["month"],a["role"]))
    if out["attachments"]:
        with ThreadPoolExecutor(max_workers=min(6,len(out["attachments"]))) as pool:
            fm={pool.submit(parse_attachment,a):a for a in out["attachments"]}
            for fut in as_completed(fm):
                parsed,err=fut.result();out["inline_rows"].extend(parsed)
                if err:out["errors"].append(err)
    out["inline_rows"].sort(key=lambda r:(r["used_date"],r["role"],r["row_id"]))
    out["parseable_attachments"]=len(out["attachments"]);out["status"]="PARSEABLE_FOUND" if out["inline_rows"] else ("FETCH_FAILED" if out["errors"] else "NO_FILES_FOUND")
    return out

def main():
    payload=json.loads(REPORT.read_text(encoding="utf-8"));fresh=discover(int(payload.get("year") or datetime.now().year))
    payload["sources"]=[x for x in payload.get("sources",[]) if x.get("key")!=KEY]+[fresh]
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"key":KEY,"status":fresh["status"],"attachments":len(fresh["attachments"]),"rows":len(fresh["inline_rows"]),
      "merchants":len({r["merchant"] for r in fresh["inline_rows"]}),"roles":sorted({r["role"] for r in fresh["inline_rows"]}),
      "errors":fresh["errors"][:5]},ensure_ascii=False))
if __name__=="__main__":main()
