#!/usr/bin/env python3
import io,re,html,zipfile,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from html.parser import HTMLParser

BASES=[
("기관장","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_01.do?articleNo=600602&mode=view"),
("감사","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_02.do?articleNo=600603&mode=view"),
("임원","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_03.do?articleNo=600604&mode=view"),
]
UA="Mozilla/5.0"
NS={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main","r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
class P(HTMLParser):
  def __init__(self): super().__init__(); self.a=[]; self.cur=None
  def handle_starttag(self,t,attrs):
    if t.lower()=="a": self.cur=dict(attrs); self.cur["text"]=[]
  def handle_data(self,d):
    if self.cur is not None:self.cur["text"].append(d)
  def handle_endtag(self,t):
    if t.lower()=="a" and self.cur is not None:
      self.cur["text"]=" ".join(" ".join(self.cur["text"]).split());self.a.append(self.cur);self.cur=None
def fetch(url,referer=""):
  req=urllib.request.Request(url,headers={"User-Agent":UA,"Referer":referer or url,"Accept-Language":"ko-KR,ko;q=0.9"})
  with urllib.request.urlopen(req,timeout=15) as r:return r.read(),r.headers.get_content_charset()
def xrows(blob):
  z=zipfile.ZipFile(io.BytesIO(blob)); shared=[]
  if "xl/sharedStrings.xml" in z.namelist():
    root=ET.fromstring(z.read("xl/sharedStrings.xml"))
    for si in root.findall("a:si",NS): shared.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
  wb=ET.fromstring(z.read("xl/workbook.xml")); rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
  relmap={r.attrib["Id"]:r.attrib["Target"] for r in rels}
  for sh in wb.find("a:sheets",NS):
    name=sh.attrib.get("name",""); rid=sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id","")
    target=relmap.get(rid,""); path=target if target.startswith("xl/") else "xl/"+target.lstrip("/")
    if path not in z.namelist(): path="xl/"+target.replace("../","").lstrip("/")
    root=ET.fromstring(z.read(path))
    print("SHEET",name)
    for row in root.findall(".//a:sheetData/a:row",NS)[:24]:
      vals=[]
      for c in row.findall("a:c",NS):
        typ=c.attrib.get("t","");v=c.find("a:v",NS);val="" if v is None else (v.text or "")
        if typ=="s" and val.isdigit() and int(val)<len(shared):val=shared[int(val)]
        elif typ=="inlineStr":val="".join(t.text or "" for t in c.iter() if t.tag.endswith("}t"))
        vals.append(f"{c.attrib.get('r','')}={val}")
      print("ROW",row.attrib.get("r")," | ".join(vals))
for role,url in BASES:
  raw,cs=fetch(url); doc=raw.decode(cs or "utf-8",errors="replace")
  p=P();p.feed(doc)
  link=next(a for a in p.a if ".xlsx" in a.get("text","").lower())
  dl=urllib.parse.urljoin(url,html.unescape(link.get("href","")))
  blob,_=fetch(dl,url)
  print("ROLE",role,"FILE",link["text"],"BYTES",len(blob),"MAGIC",blob[:4])
  xrows(blob)
