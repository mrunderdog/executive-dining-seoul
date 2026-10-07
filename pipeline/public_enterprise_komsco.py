#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import urllib.request
import io
import zipfile
import xml.etree.ElementTree as ET
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



def probe_xlsx(url:str)->list[str]:
    req=urllib.request.Request(url,headers={"User-Agent":BROWSER_UA,"Referer":"https://www.alio.go.kr/"})
    with urllib.request.urlopen(req,timeout=20) as r:
        blob=r.read()
    if blob[:2]!=b"PK":
        return [f"XLSX_BAD_MAGIC bytes={len(blob)} head={blob[:24]!r}"]
    z=zipfile.ZipFile(io.BytesIO(blob))
    ns={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    shared=[]
    if "xl/sharedStrings.xml" in z.namelist():
        root=ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("a:si",ns):
            shared.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
    wb=ET.fromstring(z.read("xl/workbook.xml"))
    rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap={r.attrib["Id"]:r.attrib["Target"] for r in rels}
    out=[f"XLSX_BYTES={len(blob)}"]
    for sh in wb.find("a:sheets",ns):
        name=sh.attrib.get("name","")
        rid=sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id","")
        target=relmap.get(rid,"")
        path=target if target.startswith("xl/") else "xl/"+target.lstrip("/")
        if path not in z.namelist():
            path="xl/"+target.replace("../","").lstrip("/")
        out.append(f"SHEET={name} path={path}")
        if path not in z.namelist():
            continue
        root=ET.fromstring(z.read(path))
        rows=[]
        for row in root.findall(".//a:sheetData/a:row",ns)[:12]:
            vals=[]
            for c in row.findall("a:c",ns):
                typ=c.attrib.get("t","")
                v=c.find("a:v",ns)
                val="" if v is None else (v.text or "")
                if typ=="s" and val.isdigit() and int(val)<len(shared):
                    val=shared[int(val)]
                elif typ=="inlineStr":
                    val="".join(t.text or "" for t in c.iter() if t.tag.endswith("}t"))
                vals.append(val)
            rows.append(" | ".join(vals))
        out.extend(f"ROW={x}" for x in rows)
    return out[:80]

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
    if out["attachments"]:
        try:
            out["diagnostics"].extend(probe_xlsx(out["attachments"][0]["url"]))
        except Exception as e:
            out["diagnostics"].append(f"XLSX_PROBE_ERROR={type(e).__name__}: {e}")
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
        "errors":fresh["errors"][:5],"diagnostics":fresh.get("diagnostics",[])[:80]
    },ensure_ascii=False))


if __name__=="__main__":
    main()
