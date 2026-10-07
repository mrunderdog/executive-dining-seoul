#!/usr/bin/env python3
from __future__ import annotations
import html,io,re,urllib.parse,urllib.request,zipfile,xml.etree.ElementTree as ET
from pypdf import PdfReader
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def req(url,data=None,referer=""):
    h={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"}
    if referer:h["Referer"]=referer
    r=urllib.request.Request(url,data=data,headers=h)
    with urllib.request.urlopen(r,timeout=30) as x:return x.read(),x.geturl(),x.headers

# KOAT xlsx
list_url="https://m.koat.or.kr/board/expenseInst/list.do"
raw,_,_=req(list_url); doc=raw.decode("utf-8","replace")
sig=re.search(r'<form name="downForm"[^>]*>\s*<input type="hidden" name="ptSignature" value="([^"]+)"',doc,re.S)
data=urllib.parse.urlencode({"ptSignature":html.unescape(sig.group(1)),"mode":"1","key":"14015"}).encode()
blob,_,_=req("https://m.koat.or.kr/download.do",data,list_url)
z=zipfile.ZipFile(io.BytesIO(blob))
NS={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main","r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
shared=[]
if "xl/sharedStrings.xml" in z.namelist():
 root=ET.fromstring(z.read("xl/sharedStrings.xml"))
 for si in root.findall("a:si",NS):shared.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
wb=ET.fromstring(z.read("xl/workbook.xml")); rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
relmap={r.attrib["Id"]:r.attrib["Target"] for r in rels}
def col(ref):
 m=re.match(r"([A-Z]+)",ref or "");return m.group(1) if m else ""
for sh in wb.find("a:sheets",NS):
 rid=sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id","")
 target=relmap.get(rid,""); path=target if target.startswith("xl/") else "xl/"+target.lstrip("/")
 if path not in z.namelist(): path="xl/"+target.replace("../","").lstrip("/")
 root=ET.fromstring(z.read(path));print("KOAT_SHEET",sh.attrib.get("name"))
 for row in root.findall(".//a:sheetData/a:row",NS)[:25]:
  vals={}
  for c in row.findall("a:c",NS):
   typ=c.attrib.get("t","");v=c.find("a:v",NS);val="" if v is None else (v.text or "")
   if typ=="s" and val.isdigit() and int(val)<len(shared):val=shared[int(val)]
   elif typ=="inlineStr":val="".join(t.text or "" for t in c.iter() if t.tag.endswith("}t"))
   vals[col(c.attrib.get("r",""))]=" ".join(str(val).split())
  print("KOAT_ROW",row.attrib.get("r"),vals)

# NILE latest PDF
nu="https://www.nile.or.kr/usr/wap/downloadFile.do?app=12716&seq=2196347&atchFileSeq=2196345&fileColumn=atchFileSeq&fileSn=0&lang=ko"
blob,u,h=req(nu,referer="https://www.nile.or.kr/usr/wap/list.do?app=12716&lang=ko&listAll=Y")
print("NILE_FILE",len(blob),u,h.get("content-type"),h.get("content-disposition"),blob[:8])
if blob[:4]==b"%PDF":
 text="\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(blob)).pages)
 print("NILE_TEXT\n",text[:18000])
