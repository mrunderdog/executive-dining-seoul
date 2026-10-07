#!/usr/bin/env python3
import io, json, zipfile, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path

REPORT=Path("reports/public-enterprise-discovery.json")
UA="Mozilla/5.0"
d=json.loads(REPORT.read_text(encoding="utf-8"))
src=next(x for x in d["sources"] if x.get("key")=="kps")
a=sorted(src.get("attachments",[]),key=lambda x:(x.get("year",0),x.get("month",0)))[-1]
req=urllib.request.Request(a["url"],headers={"User-Agent":UA,"Referer":a.get("parent","")})
with urllib.request.urlopen(req,timeout=20) as r: blob=r.read()
print("ATT",a["text"])
print("BYTES",len(blob),"MAGIC",blob[:4])
z=zipfile.ZipFile(io.BytesIO(blob))
ns={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main","r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
shared=[]
if "xl/sharedStrings.xml" in z.namelist():
    root=ET.fromstring(z.read("xl/sharedStrings.xml"))
    for si in root.findall("a:si",ns):
        shared.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
wb=ET.fromstring(z.read("xl/workbook.xml"))
rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
relmap={r.attrib["Id"]:r.attrib["Target"] for r in rels}
for sh in wb.find("a:sheets",ns):
    name=sh.attrib.get("name","")
    rid=sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id","")
    target=relmap.get(rid,"")
    path=target if target.startswith("xl/") else "xl/"+target.lstrip("/")
    if path not in z.namelist(): path="xl/"+target.replace("../","").lstrip("/")
    print("SHEET",name,path)
    root=ET.fromstring(z.read(path))
    for row in root.findall(".//a:sheetData/a:row",ns)[:35]:
        vals=[]
        for c in row.findall("a:c",ns):
            ref=c.attrib.get("r","")
            typ=c.attrib.get("t","")
            v=c.find("a:v",ns)
            val="" if v is None else (v.text or "")
            if typ=="s" and val.isdigit() and int(val)<len(shared): val=shared[int(val)]
            elif typ=="inlineStr": val="".join(t.text or "" for t in c.iter() if t.tag.endswith("}t"))
            vals.append(f"{ref}={val}")
        print("ROW",row.attrib.get("r")," | ".join(vals))
