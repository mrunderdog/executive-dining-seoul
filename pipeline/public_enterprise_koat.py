#!/usr/bin/env python3
from __future__ import annotations

import html, io, json, re, urllib.parse, urllib.request, zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="koat"
INSTITUTION="한국농업기술진흥원"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
BOARDS=[
    ("기관장","https://m.koat.or.kr/board/expenseInst/list.do"),
    ("임원","https://m.koat.or.kr/board/expenseExecutive/list.do"),
]
NS={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}

def fetch(url:str,data:bytes|None=None,referer:str="")->bytes:
    headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"}
    if referer:headers["Referer"]=referer
    req=urllib.request.Request(url,data=data,headers=headers)
    with urllib.request.urlopen(req,timeout=25) as r:
        return r.read()

def text_fetch(url:str,data:bytes|None=None)->str:
    raw=fetch(url,data)
    for enc in ("utf-8","cp949","euc-kr"):
        try:return raw.decode(enc)
        except Exception:pass
    return raw.decode("utf-8","replace")

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
    z=zipfile.ZipFile(io.BytesIO(blob));shared=[]
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
        if path not in z.namelist():
            path="xl/"+target.replace("../","").lstrip("/")
        if path not in z.namelist():
            continue
        root=ET.fromstring(z.read(path))
        for row in root.findall(".//a:sheetData/a:row",NS):
            vals={}
            for c in row.findall("a:c",NS):
                typ=c.attrib.get("t","");v=c.find("a:v",NS);val="" if v is None else (v.text or "")
                if typ=="s" and val.isdigit() and int(val)<len(shared):
                    val=shared[int(val)]
                elif typ=="inlineStr":
                    val="".join(t.text or "" for t in c.iter() if t.tag.endswith("}t"))
                vals[_col(c.attrib.get("r",""))]=" ".join(str(val).split())
            yield sh.attrib.get("name",""),int(row.attrib.get("r","0") or 0),vals

def _listing_page(url:str,page:int)->str:
    if page==1:
        return text_fetch(url)
    data=urllib.parse.urlencode({
        "currentPageNo":str(page),
        "searchCondition":"99",
        "searchKeyword":"",
    }).encode()
    return text_fetch(url,data)

def _discover_files(year:int):
    years={year,year-1};files=[];pages=[];errors=[]
    for board_role,url in BOARDS:
        for p in range(1,5):
            try:
                doc=_listing_page(url,p)
            except Exception as e:
                errors.append(f"listing {url} page {p}: {type(e).__name__}: {e}")
                continue
            pages.append(url+(f"?currentPageNo={p}" if p>1 else ""))
            sm=re.search(r'<form name="downForm"[^>]*>\s*<input type="hidden" name="ptSignature" value="([^"]+)"',doc,re.S)
            signature=html.unescape(sm.group(1)) if sm else ""
            page_years=[]
            for m in re.finditer(r"<tr\b[^>]*onclick=['\"]fn_borad_file_down\('([^']+)'\)['\"][^>]*>(.*?)</tr>",doc,re.I|re.S):
                key,body=m.group(1),m.group(2)
                txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",body)).split())
                ym=re.search(r"(20\d{2})년\s*(\d{1,2})월\s*(기관장|임원)\s*업무추진비",txt)
                if not ym:continue
                y,mo=int(ym.group(1)),int(ym.group(2))
                page_years.append(y)
                if y not in years:continue
                files.append({
                    "keyid":key,"year":y,"month":mo,"text":txt,
                    "parent":url,"signature":signature,"board_role":board_role,
                })
            if page_years and min(page_years)<min(years):
                break
    uniq={x["keyid"]:x for x in files}
    return sorted(uniq.values(),key=lambda x:(x["year"],x["month"],x["board_role"])),pages,errors

def _download(att:dict)->bytes:
    signature=att.get("signature","")
    if not signature:
        raise RuntimeError("ptSignature not found")
    data=urllib.parse.urlencode({
        "ptSignature":signature,
        "mode":"1",
        "key":att["keyid"],
    }).encode()
    return fetch("https://m.koat.or.kr/download.do",data,att["parent"])

def _parse(att:dict):
    try:
        blob=_download(att)
    except Exception as e:
        return [],f"download {att['keyid']}: {type(e).__name__}: {e}"
    rows=[]
    try:
        for sheet,ri,v in _xlsx_rows(blob):
            d=_date(v.get("B",""))
            merchant=v.get("C","").strip()
            if not d or not merchant or merchant in {"-","내부직원","외부","유관기관","사용처(가맹점명)"}:
                continue
            role=v.get("A","").strip() or att.get("board_role") or "임원"
            rows.append({
                "source_key":KEY,"institution":INSTITUTION,
                "cohort":"public_enterprise_leadership",
                "role":role,"department":"",
                "used_date":d,"used_time":"",
                "merchant":merchant,"address":"",
                "purpose":v.get("D",""),
                "people":_int(v.get("G","")),
                "amount":_int(v.get("E","")),
                "source_amount_scale":1,
                "payment_method":v.get("H",""),
                "source_category":att.get("board_role") or "임원",
                "target":"",
                "source_url":att["parent"],
                "source_sheet":sheet,"source_row":ri,
                "row_id":f"koat:{att['keyid']}:{sheet}:{ri}",
            })
    except Exception as e:
        return [],f"parse {att['keyid']}: {type(e).__name__}: {e}"
    return rows,None

def discover(year:int)->dict:
    files,pages,errors=_discover_files(year);rows=[]
    if files:
        with ThreadPoolExecutor(max_workers=min(6,len(files))) as pool:
            fm={pool.submit(_parse,a):a for a in files}
            for fut in as_completed(fm):
                parsed,err=fut.result()
                rows.extend(parsed)
                if err:errors.append(err)
    rows.sort(key=lambda r:(r["used_date"],r["role"],r["row_id"]))
    atts=[{
        "text":a["text"],
        "url":f"https://m.koat.or.kr/download.do#key={a['keyid']}",
        "download_url":f"https://m.koat.or.kr/download.do#key={a['keyid']}",
        "year":a["year"],"month":a["month"],
        "parent":a["parent"],"attachment_id":a["keyid"],
        "role":a["board_role"],
    } for a in files]
    return {
        "key":KEY,"institution":INSTITUTION,
        "cohort":"public_enterprise_leadership",
        "default_role":"원장·임원",
        "years":[year-1,year],"pages":pages,
        "attachments":atts,"inline_rows":rows,"inline_replace":True,
        "errors":errors,"parseable_attachments":len(files),
        "status":"PARSEABLE_FOUND" if rows else ("FETCH_FAILED" if errors else "NO_FILES_FOUND"),
    }

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
        "date_min":min((r["used_date"] for r in fresh["inline_rows"]),default=""),
        "date_max":max((r["used_date"] for r in fresh["inline_rows"]),default=""),
        "errors":fresh["errors"][:8],
    },ensure_ascii=False))

if __name__=="__main__":
    main()
