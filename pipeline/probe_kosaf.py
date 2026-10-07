#!/usr/bin/env python3
from __future__ import annotations
import io,re,urllib.request,zipfile,xml.etree.ElementTree as ET
UA="Mozilla/5.0"
BASE="https://www.kosaf.go.kr/ko/openinfo.do?ctgrId1=0000000015&pg=operation10"
DL="https://www.kosaf.go.kr/ko/download.do?pPath=HP.BRD.UPLOAD&pSeq_No=21321&pFile_No=1"
req=urllib.request.Request(DL,headers={"User-Agent":UA,"Referer":BASE})
with urllib.request.urlopen(req,timeout=20) as r:
    blob=r.read(); print("DOWNLOAD",len(blob),r.geturl(),r.headers.get("content-type"),r.headers.get("content-disposition"))
print("MAGIC",blob[:8])
z=zipfile.ZipFile(io.BytesIO(blob))
NS={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main","r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
shared=[]
if "xl/sharedStrings.xml" in z.namelist():
    root=ET.fromstring(z.read("xl/sharedStrings.xml"))
    for si in root.findall("a:si",NS):
        shared.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
wb=ET.fromstring(z.read("xl/workbook.xml"))
rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
relmap={r.attrib["Id"]:r.attrib["Target"] for r in rels}
def col(ref):
    m=re.match(r"([A-Z]+)",ref or ""); return m.group(1) if m else ""
for sh in wb.find("a:sheets",NS):
    rid=sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id","")
    target=relmap.get(rid,"")
    path=target if target.startswith("xl/") else "xl/"+target.lstrip("/")
    if path not in z.namelist(): path="xl/"+target.replace("../","").lstrip("/")
    print("SHEET",sh.attrib.get("name"),path)
    root=ET.fromstring(z.read(path))
    for row in root.findall(".//a:sheetData/a:row",NS)[:30]:
        vals={}
        for cell in row.findall("a:c",NS):
            typ=cell.attrib.get("t",""); v=cell.find("a:v",NS)
            val="" if v is None else (v.text or "")
            if typ=="s" and val.isdigit() and int(val)<len(shared): val=shared[int(val)]
            elif typ=="inlineStr": val="".join(t.text or "" for t in cell.iter() if t.tag.endswith("}t"))
            vals[col(cell.attrib.get("r",""))]=" ".join(str(val).split())
        print(row.attrib.get("r"),vals)
