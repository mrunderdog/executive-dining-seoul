#!/usr/bin/env python3
import io,json,zipfile,urllib.request,xml.etree.ElementTree as ET,re
from collections import Counter
from pathlib import Path
from datetime import datetime,timedelta

REPORT=Path("reports/public-enterprise-discovery.json")
UA="Mozilla/5.0"
d=json.loads(REPORT.read_text(encoding="utf-8"))
src=next(x for x in d["sources"] if x.get("key")=="kps")
ns={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main","r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
roles=Counter(); rows=[]

def col(ref):
    m=re.match(r"([A-Z]+)",ref or "")
    return m.group(1) if m else ""

def workbook_rows(blob):
    z=zipfile.ZipFile(io.BytesIO(blob)); shared=[]
    if "xl/sharedStrings.xml" in z.namelist():
        root=ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("a:si",ns):
            shared.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
    wb=ET.fromstring(z.read("xl/workbook.xml")); rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap={r.attrib["Id"]:r.attrib["Target"] for r in rels}
    for sh in wb.find("a:sheets",ns):
        rid=sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id",""); target=relmap.get(rid,"")
        path=target if target.startswith("xl/") else "xl/"+target.lstrip("/")
        if path not in z.namelist(): path="xl/"+target.replace("../","").lstrip("/")
        if path not in z.namelist(): continue
        root=ET.fromstring(z.read(path))
        for row in root.findall(".//a:sheetData/a:row",ns):
            vals={}
            for c in row.findall("a:c",ns):
                typ=c.attrib.get("t",""); v=c.find("a:v",ns); val="" if v is None else (v.text or "")
                if typ=="s" and val.isdigit() and int(val)<len(shared): val=shared[int(val)]
                elif typ=="inlineStr": val="".join(t.text or "" for t in c.iter() if t.tag.endswith("}t"))
                vals[col(c.attrib.get("r",""))]=val.strip()
            yield vals

failures=[]
for a in sorted(src.get("attachments",[]),key=lambda x:(x.get("year",0),x.get("month",0))):
    try:
        req=urllib.request.Request(a["url"],headers={"User-Agent":UA,"Referer":a.get("parent","")})
        with urllib.request.urlopen(req,timeout=12) as r: blob=r.read()
    except Exception as e:
        failures.append(f"{a.get('year')}-{a.get('month'):02d}:{type(e).__name__}:{e}")
        continue
    file_rows=list(workbook_rows(blob))
    header_seen=False
    for v in file_rows:
        if v.get("A")=="부서명" and v.get("B")=="집행자":
            header_seen=True; continue
        if not header_seen: continue
        role=v.get("B","").strip()
        if not role or role=="계": continue
        merchant=v.get("F","").strip()
        purpose=v.get("D","").strip()
        if not merchant and not purpose: continue
        roles[role]+=1
        if len(rows)<120:
            rows.append({"ym":f"{a.get('year')}-{a.get('month'):02d}","dept":v.get("A",""),"role":role,"date":v.get("C",""),"purpose":purpose,"merchant":merchant,"amount":v.get("E",""),"target":v.get("G",""),"method":v.get("H",""),"people":v.get("I","")})
print("ROLE_COUNTS",json.dumps(roles,ensure_ascii=False,sort_keys=True))
print("FAILURES",json.dumps(failures,ensure_ascii=False))
for r in rows: print("DATA",json.dumps(r,ensure_ascii=False))
