#!/usr/bin/env python3
import re, urllib.request, urllib.parse, html, io, zipfile, xml.etree.ElementTree as ET
from html.parser import HTMLParser
UA="Mozilla/5.0"
URLS=[
 ("기관장","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_01.do"),
 ("감사","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_02.do"),
 ("임원","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_03.do"),
]
class P(HTMLParser):
    def __init__(self): super().__init__(); self.a=[]; self.cur=None
    def handle_starttag(self,tag,attrs):
        if tag.lower()=="a":
            d=dict(attrs); self.cur={"href":d.get("href",""),"onclick":d.get("onclick",""),"text":[]}
    def handle_data(self,d):
        if self.cur is not None:self.cur["text"].append(d)
    def handle_endtag(self,tag):
        if tag.lower()=="a" and self.cur is not None:
            self.cur["text"]=" ".join(" ".join(self.cur["text"]).split());self.a.append(self.cur);self.cur=None

def fetch(url,binary=False,referer=""):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Referer":referer or url})
    with urllib.request.urlopen(req,timeout=15) as r:
        raw=r.read()
        return raw if binary else raw.decode(r.headers.get_content_charset() or "utf-8","replace")

def preview_xlsx(blob):
    z=zipfile.ZipFile(io.BytesIO(blob))
    ns={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main","r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    shared=[]
    if "xl/sharedStrings.xml" in z.namelist():
        root=ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("a:si",ns):
            shared.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
    wb=ET.fromstring(z.read("xl/workbook.xml")); rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap={r.attrib["Id"]:r.attrib["Target"] for r in rels}
    out=[]
    for sh in wb.find("a:sheets",ns):
        rid=sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id",""); target=relmap.get(rid,"")
        path=target if target.startswith("xl/") else "xl/"+target.lstrip("/")
        if path not in z.namelist(): path="xl/"+target.replace("../","").lstrip("/")
        if path not in z.namelist(): continue
        root=ET.fromstring(z.read(path))
        out.append("SHEET="+sh.attrib.get("name",""))
        for row in root.findall(".//a:sheetData/a:row",ns)[:15]:
            vals=[]
            for c in row.findall("a:c",ns):
                ref=c.attrib.get("r","");typ=c.attrib.get("t","");v=c.find("a:v",ns);val="" if v is None else (v.text or "")
                if typ=="s" and val.isdigit() and int(val)<len(shared): val=shared[int(val)]
                elif typ=="inlineStr": val="".join(t.text or "" for t in c.iter() if t.tag.endswith("}t"))
                vals.append(f"{ref}={val}")
            out.append("ROW "+row.attrib.get("r","")+" "+" | ".join(vals))
        break
    return out

for role,base in URLS:
    doc=fetch(base)
    m=re.search(r'href=["\']([^"\']*mode=view&articleNo=(\d+)[^"\']*)["\'][^>]*>\s*2026년도\s*8월\s*업무추진비',doc,re.I|re.S)
    if not m:
        print("NO_DETAIL",role); continue
    detail=urllib.parse.urljoin(base,html.unescape(m.group(1)))
    ddoc=fetch(detail)
    print("DETAIL",role,detail,"LEN",len(ddoc))
    p=P();p.feed(ddoc)
    for a in p.a:
        blob=(a["text"]+" "+a["href"]+" "+a["onclick"])
        if re.search(r"xlsx|xls|download|attach|file",blob,re.I):
            u=urllib.parse.urljoin(detail,html.unescape(a["href"]))
            print("FILELINK",role,repr(a["text"]),repr(u),repr(a["onclick"]))
            if re.search(r"\.xlsx?(?:$|\?)",u,re.I) or "download" in u.lower():
                try:
                    data=fetch(u,binary=True,referer=detail)
                    print("FILEBYTES",role,len(data),data[:4])
                    if data[:2]==b"PK":
                        for line in preview_xlsx(data): print("XLSX",role,line)
                except Exception as e:
                    print("FILEERR",role,type(e).__name__,e)
