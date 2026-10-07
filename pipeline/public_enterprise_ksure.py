#!/usr/bin/env python3
from __future__ import annotations
import html, io, json, re, urllib.parse, urllib.request, zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="ksure"
INSTITUTION="한국무역보험공사"
LISTING="https://www.ksure.or.kr/rh-kr/bbs/i-480/list.do"
UA="Mozilla/5.0"
NS={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}

def fetch(url:str,referer:str="")->bytes:
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Referer":referer or LISTING,"Accept-Language":"ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req,timeout=12) as r:return r.read()

def text_fetch(url:str)->str:
    raw=fetch(url)
    for enc in ("utf-8","cp949","euc-kr"):
        try:return raw.decode(enc)
        except Exception:pass
    return raw.decode("utf-8",errors="replace")

def _col(ref:str)->str:
    m=re.match(r"([A-Z]+)",ref or "");return m.group(1) if m else ""

def _date(v:str)->str:
    try:
        n=float(v)
        if 30000<=n<=60000:return (datetime(1899,12,30)+timedelta(days=n)).date().isoformat()
    except Exception:pass
    s=" ".join(str(v or "").split())
    m=re.search(r"(20\d{2})-(\d{1,2})-(\d{1,2})",s)
    if not m:return ""
    try:return datetime(int(m.group(1)),int(m.group(2)),int(m.group(3))).date().isoformat()
    except ValueError:return ""

def _to_int(v):
    try:return int(round(float(str(v).replace(",",""))))
    except Exception:return None

def _xlsx_rows(blob:bytes):
    z=zipfile.ZipFile(io.BytesIO(blob));shared=[]
    if "xl/sharedStrings.xml" in z.namelist():
        root=ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("a:si",NS):
            shared.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
    wb=ET.fromstring(z.read("xl/workbook.xml"))
    rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap={r.attrib["Id"]:r.attrib["Target"] for r in rels}
    for sh in wb.find("a:sheets",NS):
        sheet=sh.attrib.get("name","")
        rid=sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id","")
        target=relmap.get(rid,"")
        path=target if target.startswith("xl/") else "xl/"+target.lstrip("/")
        if path not in z.namelist():path="xl/"+target.replace("../","").lstrip("/")
        if path not in z.namelist():continue
        root=ET.fromstring(z.read(path))
        for row in root.findall(".//a:sheetData/a:row",NS):
            vals={}
            for c in row.findall("a:c",NS):
                typ=c.attrib.get("t","");v=c.find("a:v",NS);val="" if v is None else (v.text or "")
                if typ=="s" and val.isdigit() and int(val)<len(shared):val=shared[int(val)]
                elif typ=="inlineStr":val="".join(t.text or "" for t in c.iter() if t.tag.endswith("}t"))
                vals[_col(c.attrib.get("r",""))]=" ".join(str(val).split())
            yield sheet,int(row.attrib.get("r","0") or 0),vals

def _discover_files(year:int):
    doc=text_fetch(LISTING);years={year,year-1};files=[]
    for dm in re.finditer(r'href=["\']([^"\']*?down\.do\?[^"\']+)["\']',doc,re.I):
        start=max(0,dm.start()-1800);end=min(len(doc),dm.end()+500)
        window=html.unescape(re.sub(r"<[^>]+>"," ",doc[start:end]))
        matches=list(re.finditer(r"(20\d{2})년\s*(기관장|상임감사|상임이사)\s*업무추진비",window))
        if not matches:continue
        y=int(matches[-1].group(1));role=matches[-1].group(2)
        if y not in years:continue
        url=urllib.parse.urljoin(LISTING,html.unescape(dm.group(1)))
        q=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        files.append({"text":f"{y}년 {role} 업무추진비.xlsx","role":role,"year":y,"month":None,
                      "url":url,"download_url":url,"parent":LISTING,
                      "attachment_id":f"{q.get('ntt_sn',[''])[0]}|{q.get('atfile_sn',[''])[0]}"})
    uniq={x["url"]:x for x in files}
    return sorted(uniq.values(),key=lambda x:(x["year"],x["role"]))

def _parse(att:dict):
    try:blob=fetch(att["url"],att.get("parent",""))
    except Exception as e:return [],f"download {att['url']}: {type(e).__name__}: {e}"
    rows=[]
    for sheet,ri,v in _xlsx_rows(blob):
        d=_date(v.get("A",""))
        if not d:continue
        purpose=v.get("B","");merchant=v.get("C","")
        if not merchant or merchant=="-":continue
        rows.append({
            "source_key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
            "role":att["role"],"department":"","used_date":d,"used_time":"",
            "merchant":merchant,"address":"","purpose":purpose,
            "people":_to_int(v.get("F","")),"amount":_to_int(v.get("G","")),
            "source_amount_scale":1,"payment_method":v.get("E",""),"source_category":"",
            "target":v.get("D",""),"source_url":att["url"],"source_sheet":sheet,"source_row":ri,
            "row_id":f"ksure:{att['attachment_id']}:{sheet}:{ri}",
        })
    return rows,None

def discover(year:int)->dict:
    attachments=_discover_files(year)
    out={"key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
         "default_role":"기관장·상임감사·상임이사","years":[year-1,year],"pages":[LISTING],
         "attachments":attachments,"inline_rows":[],"inline_replace":True,"errors":[]}
    if attachments:
        with ThreadPoolExecutor(max_workers=min(6,len(attachments))) as pool:
            fm={pool.submit(_parse,a):a for a in attachments}
            for fut in as_completed(fm):
                parsed,err=fut.result();out["inline_rows"].extend(parsed)
                if err:out["errors"].append(err)
    out["inline_rows"].sort(key=lambda r:(r["used_date"],r["role"],r["row_id"]))
    out["parseable_attachments"]=len(attachments)
    out["status"]="PARSEABLE_FOUND" if out["inline_rows"] else ("FETCH_FAILED" if out["errors"] else "NO_FILES_FOUND")
    return out

def main():
    payload=json.loads(REPORT.read_text(encoding="utf-8"));fresh=discover(int(payload.get("year") or datetime.now().year))
    payload["sources"]=[x for x in payload.get("sources",[]) if x.get("key")!=KEY]+[fresh]
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"key":KEY,"status":fresh["status"],"attachments":len(fresh["attachments"]),
      "rows":len(fresh["inline_rows"]),"merchants":len({r["merchant"] for r in fresh["inline_rows"]}),
      "roles":sorted({r["role"] for r in fresh["inline_rows"]}),"errors":fresh["errors"][:5]},ensure_ascii=False))
if __name__=="__main__":main()
