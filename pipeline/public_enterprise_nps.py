#!/usr/bin/env python3
from __future__ import annotations
import html, io, json, re, urllib.parse, urllib.request, zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="nps"
INSTITUTION="국민연금공단"
LISTING="https://www.nps.or.kr/pbcpgdnc/bzadpblnt/getOHAG0028M0List.do?menuId=MN24001026"
UA="Mozilla/5.0"
NS={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
ROLE_RE=re.compile(r"(이사장|감사|기획이사|연금이사|복지이사|기금이사|연구원장|AI디지털혁신본부장)")

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
    m=re.search(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})",s)
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
    years={year,year-1};files=[];pages=[];errors=[]
    urls=[LISTING]+[LISTING+f"&currentPage={p}" for p in range(2,21)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        fm={pool.submit(text_fetch,u):u for u in urls}
        for fut in as_completed(fm):
            u=fm[fut]
            try:doc=fut.result()
            except Exception as e:
                errors.append(f"listing {u}: {type(e).__name__}: {e}");continue
            pages.append(u)
            for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
                txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
                ym=re.search(r"(20\d{2})년\s*(\d{1,2})월\s*(.+?)\s*업무추진비",txt)
                if not ym:continue
                y,m=int(ym.group(1)),int(ym.group(2))
                if y not in years:continue
                rm=ROLE_RE.search(ym.group(3))
                if not rm:continue
                role=rm.group(1)
                fm_call=re.search(r"fncAtchFileDownload\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",row,re.I)
                if not fm_call:continue
                fid,sn=fm_call.group(1),fm_call.group(2)
                dl=f"https://www.nps.or.kr/fileDown.do?atchFileId={urllib.parse.quote(fid)}&atchFileSn={urllib.parse.quote(sn)}"
                files.append({"text":txt,"role":role,"year":y,"month":m,"url":dl,"download_url":dl,
                              "parent":u,"attachment_id":f"{fid}|{sn}"})
    uniq={x["attachment_id"]:x for x in files}
    return sorted(uniq.values(),key=lambda x:(x["year"],x["month"],x["role"])),pages,errors

def _parse(att:dict):
    try:blob=fetch(att["url"],att.get("parent",""))
    except Exception as e:return [],f"download {att['url']}: {type(e).__name__}: {e}"
    rows=[]
    for sheet,ri,v in _xlsx_rows(blob):
        d=_date(v.get("B",""))
        if not d:continue
        merchant=v.get("D","");purpose=v.get("C","")
        if not merchant or merchant=="-":continue
        rows.append({
            "source_key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
            "role":att["role"],"department":"","used_date":d,"used_time":"",
            "merchant":merchant,"address":"","purpose":purpose,
            "people":_to_int(v.get("G","")),"amount":_to_int(v.get("H","")),
            "source_amount_scale":1,"payment_method":v.get("F",""),"source_category":"",
            "target":v.get("E",""),"source_url":att["url"],"source_sheet":sheet,"source_row":ri,
            "row_id":f"nps:{att['attachment_id']}:{sheet}:{ri}",
        })
    return rows,None

def discover(year:int)->dict:
    attachments,pages,errors=_discover_files(year)
    out={"key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
         "default_role":"임원·본부장","years":[year-1,year],"pages":pages,
         "attachments":attachments,"inline_rows":[],"inline_replace":True,"errors":errors}
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
    payload=json.loads(REPORT.read_text(encoding="utf-8"));fresh=discover(int(payload.get("year") or datetime.now().year))
    payload["sources"]=[x for x in payload.get("sources",[]) if x.get("key")!=KEY]+[fresh]
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"key":KEY,"status":fresh["status"],"attachments":len(fresh["attachments"]),
      "rows":len(fresh["inline_rows"]),"merchants":len({r["merchant"] for r in fresh["inline_rows"]}),
      "roles":sorted({r["role"] for r in fresh["inline_rows"]}),"errors":fresh["errors"][:8]},ensure_ascii=False))
if __name__=="__main__":main()
