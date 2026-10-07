#!/usr/bin/env python3
from __future__ import annotations

import html
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

from public_enterprise_discovery import decode

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="kps"
INSTITUTION="한전KPS"
LISTING="https://www.kps.co.kr/web/integrity/clean/expense.do"
METADATA="https://www.data.go.kr/data/15151716/fileData.do"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"


def fetch(url:str)->str:
    req=urllib.request.Request(url,headers={
        "User-Agent":UA,
        "Accept":"text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language":"ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
        "Referer":LISTING,
    })
    with urllib.request.urlopen(req,timeout=18) as r:
        return decode(r.read(),r.headers.get_content_charset())


def _title_text(fragment:str)->str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>"," ",fragment or "")).split())


def _listing_rows(doc:str,years:set[int])->list[dict]:
    out=[]
    for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
        idm=re.search(r"pf_DetailMove\(\s*['\"]?(\d+)['\"]?\s*\)",row,re.I)
        tm=re.search(r'<div[^>]+class=["\'][^"\']*\btitle\b[^"\']*["\'][^>]*>(.*?)</div>',row,re.I|re.S)
        if not idm or not tm:
            continue
        title=_title_text(tm.group(1))
        ym=re.search(r"(20\d{2})년\s*(\d{1,2})월",title)
        if not ym:
            continue
        year,month=int(ym.group(1)),int(ym.group(2))
        if year not in years:
            continue
        out.append({"pst_no":idm.group(1),"title":title,"year":year,"month":month})
    return out


def _detail_attachment(item:dict)->tuple[dict|None,str|None,str]:
    pst_no=item["pst_no"]
    detail=f"https://www.kps.co.kr/web/Board/{pst_no}/detailView.do?pageIndex=1&menu=2499"
    try:
        doc=fetch(detail)
    except Exception as e:
        return None,f"detail {detail}: {type(e).__name__}: {e}",detail

    # Each expense post carries one XLSX attachment in a file-list item.
    blocks=re.findall(r"<li\b.*?</li>",doc,re.I|re.S)
    for block in blocks:
        dm=re.search(r"cf_download\(\s*['\"]([^'\"]+)['\"]\s*\)",block,re.I)
        fm=re.search(r'class=["\'][^"\']*\bbtn-file\b[^"\']*["\'][^>]*>(.*?)</div>',block,re.I|re.S)
        if not dm or not fm:
            continue
        filename=_title_text(fm.group(1))
        if not re.search(r"\.xlsx?$",filename,re.I):
            continue
        token=dm.group(1)
        download="https://www.kps.co.kr/async/MultiFile/download.do?file="+urllib.parse.quote(token,safe="")
        return {
            "text":f"{item['title']} {filename}",
            "url":download,
            "download_url":download,
            "year":item["year"],
            "month":item["month"],
            "parent":detail,
            "attachment_id":f"{pst_no}|{item['year']}-{item['month']:02d}",
        },None,detail
    return None,f"attachment missing: {detail}",detail


NS={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main","r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
EXEC_RE=re.compile(r"(?:^|\\s)(?:사장|부사장|상임감사|감사|상임이사|이사|전무|상무)(?:$|\\s)")

def _col(ref:str)->str:
    m=re.match(r"([A-Z]+)",ref or "")
    return m.group(1) if m else ""

def _download_bytes(url:str,parent:str)->bytes:
    req=urllib.request.Request(url,headers={
        "User-Agent":UA,
        "Accept":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
        "Referer":parent,
    })
    with urllib.request.urlopen(req,timeout=15) as r:
        return r.read()

def _xlsx_rows(blob:bytes):
    z=zipfile.ZipFile(io.BytesIO(blob))
    shared=[]
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
        if path not in z.namelist():
            path="xl/"+target.replace("../","").lstrip("/")
        if path not in z.namelist():
            continue
        root=ET.fromstring(z.read(path))
        for row in root.findall(".//a:sheetData/a:row",NS):
            vals={}
            for c in row.findall("a:c",NS):
                typ=c.attrib.get("t","")
                v=c.find("a:v",NS)
                val="" if v is None else (v.text or "")
                if typ=="s" and val.isdigit() and int(val)<len(shared):
                    val=shared[int(val)]
                elif typ=="inlineStr":
                    val="".join(t.text or "" for t in c.iter() if t.tag.endswith("}t"))
                vals[_col(c.attrib.get("r",""))]=str(val).strip()
            yield sheet,int(row.attrib.get("r","0") or 0),vals

def _excel_date(value:str)->str:
    try:
        n=float(value)
        if 30000 <= n <= 60000:
            return (datetime(1899,12,30)+timedelta(days=n)).date().isoformat()
    except Exception:
        pass
    text=" ".join(str(value or "").split())
    m=re.search(r"(20\\d{2})[-./년\\s]+(\\d{1,2})[-./월\\s]+(\\d{1,2})",text)
    if not m:
        return ""
    try:
        return datetime(int(m.group(1)),int(m.group(2)),int(m.group(3))).date().isoformat()
    except ValueError:
        return ""

def _to_int(value,scale=1):
    try:
        return int(round(float(str(value).replace(",",""))*scale))
    except Exception:
        return None

def _parse_executive_rows(att:dict)->tuple[list[dict],str|None]:
    try:
        blob=_download_bytes(att["url"],att.get("parent",""))
    except Exception as e:
        return [],f"download {att['url']}: {type(e).__name__}: {e}"
    out=[]
    header=False
    for sheet,ri,v in _xlsx_rows(blob):
        if v.get("A")=="부서명" and v.get("B")=="집행자" and "장소" in v.get("F",""):
            header=True
            continue
        if not header:
            continue
        role=" ".join(v.get("B","").split())
        if not role or not EXEC_RE.search(role):
            continue
        merchant=" ".join(v.get("F","").split())
        purpose=" ".join(v.get("D","").split())
        used_date=_excel_date(v.get("C",""))
        if not merchant or not used_date:
            continue
        amount=_to_int(v.get("E",""),1000)
        people=_to_int(v.get("I",""),1)
        row_id=f"kps:{att.get('attachment_id','')}:{sheet}:{ri}"
        out.append({
            "source_key":KEY,"institution":INSTITUTION,
            "cohort":"public_enterprise_leadership",
            "role":role,"department":" ".join(v.get("A","").split()),
            "used_date":used_date,"used_time":"",
            "merchant":merchant,"address":"",
            "purpose":purpose,"people":people,"amount":amount,
            "source_amount_scale":1000,
            "payment_method":" ".join(v.get("H","").split()),
            "source_category":"업무추진비",
            "source_url":att["url"],"source_sheet":sheet,"source_row":ri,
            "target":" ".join(v.get("G","").split()),
            "row_id":row_id,
        })
    return out,None

def discover(year:int)->dict:
    years={year,year-1}
    out={
        "key":KEY,
        "institution":INSTITUTION,
        "cohort":"public_enterprise_leadership",
        "default_role":"임원",
        "years":sorted(years),
        "pages":[],
        "attachments":[],
        "inline_rows":[],
        "inline_replace":True,
        "errors":[],
        "metadata_url":METADATA,
    }

    items={}
    for page in range(1,5):
        url=LISTING if page==1 else f"{LISTING}?pageIndex={page}"
        try:
            doc=fetch(url)
            out["pages"].append(url)
        except Exception as e:
            out["errors"].append(f"listing {url}: {type(e).__name__}: {e}")
            continue
        for item in _listing_rows(doc,years):
            items[item["pst_no"]]=item

    details=list(items.values())
    with ThreadPoolExecutor(max_workers=min(6,max(1,len(details)))) as pool:
        fm={pool.submit(_detail_attachment,item):item for item in details}
        for fut in as_completed(fm):
            att,err,detail=fut.result()
            out["pages"].append(detail)
            if att:
                out["attachments"].append(att)
            if err:
                out["errors"].append(err)

    out["pages"]=list(dict.fromkeys(out["pages"]))
    out["attachments"].sort(key=lambda x:(x.get("year") or 0,x.get("month") or 0,x.get("attachment_id") or ""))
    for att in out["attachments"]:
        parsed,err=_parse_executive_rows(att)
        out["inline_rows"].extend(parsed)
        if err:
            out["errors"].append(err)
    out["parseable_attachments"]=len(out["attachments"])
    out["status"]="PARSEABLE_FOUND" if out["attachments"] else ("FETCH_FAILED" if out["errors"] else "NO_FILES_FOUND")
    return out


def main()->None:
    if not REPORT.exists():
        raise SystemExit("run public_enterprise_discovery.py first")
    payload=json.loads(REPORT.read_text(encoding="utf-8"))
    fresh=discover(int(payload.get("year") or datetime.now().year))
    payload["sources"]=[x for x in payload.get("sources",[]) if x.get("key")!=KEY]+[fresh]
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
        "key":KEY,
        "status":fresh["status"],
        "pages":len(fresh["pages"]),
        "attachments":len(fresh["attachments"]),
        "rows":len(fresh.get("inline_rows",[])),
        "roles":sorted({x.get("role","") for x in fresh.get("inline_rows",[]) if x.get("role")}),
        "errors":fresh["errors"][:5],
        "months":[f"{x['year']}-{x['month']:02d}" for x in fresh["attachments"]],
    },ensure_ascii=False))


if __name__=="__main__":
    main()
