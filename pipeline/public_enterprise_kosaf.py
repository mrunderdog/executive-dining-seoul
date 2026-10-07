#!/usr/bin/env python3
from __future__ import annotations

import html, io, json, re, urllib.parse, urllib.request, zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="kosaf"
INSTITUTION="한국장학재단"
LISTING="https://www.kosaf.go.kr/ko/openinfo.do?ctgrId1=0000000015&pg=operation10"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
NS={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
ROLE_RE=re.compile(r"(기관장|상임감사|상임이사)")

def fetch(url:str, binary:bool=False, referer:str=""):
    req=urllib.request.Request(url,headers={
        "User-Agent":UA,
        "Accept-Language":"ko-KR,ko;q=0.9",
        "Referer":referer or LISTING,
    })
    with urllib.request.urlopen(req,timeout=20) as r:
        raw=r.read()
        return raw if binary else raw.decode(r.headers.get_content_charset() or "utf-8","replace")

def _col(ref:str)->str:
    m=re.match(r"([A-Z]+)",ref or "")
    return m.group(1) if m else ""

def _date(v:str)->str:
    s=" ".join(str(v or "").split())
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

def _int(v):
    try:return int(round(float(str(v or "").replace(",","").strip())))
    except Exception:return None

def _xlsx_rows(blob:bytes):
    z=zipfile.ZipFile(io.BytesIO(blob)); shared=[]
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
    years={year,year-1}; files=[]; pages=[]; errors=[]
    urls=[LISTING]+[LISTING+f"&page={p}" for p in range(2,18)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        fm={pool.submit(fetch,u):u for u in urls}
        for fut in as_completed(fm):
            u=fm[fut]
            try:doc=fut.result()
            except Exception as e:
                errors.append(f"listing {u}: {type(e).__name__}: {e}");continue
            pages.append(u)
            for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
                txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
                ym=re.search(r"(20\d{2})년도\s*(\d{1,2})월\s*(기관장|상임감사|상임이사)\s*업무추진비",txt)
                if not ym:continue
                y,m,role=int(ym.group(1)),int(ym.group(2)),ym.group(3)
                if y not in years:continue
                dm=re.search(r"fileDown\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",row,re.I)
                if not dm:continue
                path,seq,file_no=dm.groups()
                dl="https://www.kosaf.go.kr/ko/download.do?"+urllib.parse.urlencode({
                    "pPath":path,"pSeq_No":seq,"pFile_No":file_no
                })
                files.append({
                    "text":txt,"role":role,"year":y,"month":m,
                    "url":dl,"download_url":dl,"parent":u,
                    "attachment_id":f"{path}|{seq}|{file_no}",
                })
    uniq={x["attachment_id"]:x for x in files}
    return sorted(uniq.values(),key=lambda x:(x["year"],x["month"],x["role"])),pages,errors

def _parse(att:dict):
    try:blob=fetch(att["url"],True,att.get("parent",""))
    except Exception as e:return [],f"download {att['url']}: {type(e).__name__}: {e}"
    rows=[]
    try:
        for sheet,ri,v in _xlsx_rows(blob):
            # Canonical KOSAF layout:
            # A date / B purpose / C merchant / D target / E people / F amount
            d=_date(v.get("A",""))
            merchant=v.get("C","").strip()
            purpose=v.get("B","").strip()
            if not d or not merchant or merchant in {"-","사용처(장소)"}:continue
            rows.append({
                "source_key":KEY,"institution":INSTITUTION,
                "cohort":"public_enterprise_leadership",
                "role":att["role"],"department":"",
                "used_date":d,"used_time":"",
                "merchant":merchant,"address":"","purpose":purpose,
                "people":_int(v.get("E","")),"amount":_int(v.get("F","")),
                "source_amount_scale":1,"payment_method":"",
                "source_category":att["role"],"target":v.get("D",""),
                "source_url":att["url"],"source_sheet":sheet,"source_row":ri,
                "row_id":f"kosaf:{att['attachment_id']}:{sheet}:{ri}",
            })
    except Exception as e:
        return [],f"parse {att['url']}: {type(e).__name__}: {e}"
    return rows,None

def discover(year:int)->dict:
    attachments,pages,errors=_discover_files(year)
    out={
        "key":KEY,"institution":INSTITUTION,
        "cohort":"public_enterprise_leadership",
        "default_role":"기관장·상임감사·상임이사",
        "years":[year-1,year],"pages":pages,
        "attachments":attachments,"inline_rows":[],
        "inline_replace":True,"errors":errors,
    }
    if attachments:
        with ThreadPoolExecutor(max_workers=min(8,len(attachments))) as pool:
            fm={pool.submit(_parse,a):a for a in attachments}
            for fut in as_completed(fm):
                parsed,err=fut.result();out["inline_rows"].extend(parsed)
                if err:out["errors"].append(err)
    out["inline_rows"].sort(key=lambda r:(r["used_date"],r["role"],r["row_id"]))
    out["parseable_attachments"]=len(attachments)
    out["status"]="PARSEABLE_FOUND" if out["inline_rows"] else ("FETCH_FAILED" if out["errors"] else "NO_FILES_FOUND")
    return out

def main():
    payload=json.loads(REPORT.read_text(encoding="utf-8"))
    fresh=discover(int(payload.get("year") or datetime.now().year))
    payload["sources"]=[x for x in payload.get("sources",[]) if x.get("key")!=KEY]+[fresh]
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
        "key":KEY,"status":fresh["status"],
        "attachments":len(fresh["attachments"]),
        "rows":len(fresh["inline_rows"]),
        "merchants":len({r["merchant"] for r in fresh["inline_rows"]}),
        "roles":sorted({r["role"] for r in fresh["inline_rows"]}),
        "errors":fresh["errors"][:8],
    },ensure_ascii=False))

if __name__=="__main__":main()
