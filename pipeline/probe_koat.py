#!/usr/bin/env python3
from __future__ import annotations
import html,io,re,urllib.parse,urllib.request,zipfile,xml.etree.ElementTree as ET
BASES=[
 ("기관장","https://m.koat.or.kr/board/expenseInst/list.do"),
 ("임원","https://m.koat.or.kr/board/expenseExecutive/list.do"),
]
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
NS={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main","r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}

def request(url,data=None,referer=""):
    headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"}
    if referer:headers["Referer"]=referer
    req=urllib.request.Request(url,data=data,headers=headers)
    with urllib.request.urlopen(req,timeout=20) as r:return r.read(),r.geturl(),r.headers

def text_fetch(url):
    raw,final,h=request(url)
    return raw.decode(h.get_content_charset() or "utf-8","replace"),final,h

def inspect_xlsx(blob):
    z=zipfile.ZipFile(io.BytesIO(blob));shared=[]
    if "xl/sharedStrings.xml" in z.namelist():
      root=ET.fromstring(z.read("xl/sharedStrings.xml"))
      for si in root.findall("a:si",NS):shared.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
    wb=ET.fromstring(z.read("xl/workbook.xml")); rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels")); relmap={r.attrib["Id"]:r.attrib["Target"] for r in rels}
    for sh in wb.find("a:sheets",NS):
      rid=sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id",""); target=relmap.get(rid,"")
      path=target if target.startswith("xl/") else "xl/"+target.lstrip("/")
      if path not in z.namelist():path="xl/"+target.replace("../","").lstrip("/")
      if path not in z.namelist():continue
      print("SHEET",sh.attrib.get("name"))
      root=ET.fromstring(z.read(path))
      for row in root.findall(".//a:sheetData/a:row",NS)[:20]:
        vals=[]
        for c in row.findall("a:c",NS):
          typ=c.attrib.get("t","");v=c.find("a:v",NS);val="" if v is None else (v.text or "")
          if typ=="s" and val.isdigit() and int(val)<len(shared):val=shared[int(val)]
          elif typ=="inlineStr":val="".join(t.text or "" for t in c.iter() if t.tag.endswith("}t"))
          vals.append(" ".join(str(val).split()))
        print("XR",row.attrib.get("r"),vals)

for role,url in BASES:
    print("\nBOARD",role,url)
    doc,final,h=text_fetch(url); print("STATUS",len(doc),final)
    sigs=re.findall(r'name=["\']ptSignature["\']\s+value=["\']([^"\']+)["\']',doc,re.I)
    rows=[]
    for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
      txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
      km=re.search(r"fn_borad_file_down\(['\"]([^'\"]+)['\"]\)",row,re.I)
      if km: rows.append((km.group(1),txt))
    print("SIGS",len(sigs),"ROWS",rows[:8])
    for key,txt in rows[:2]:
      ok=False
      for si,sig in enumerate(sigs[:3]):
        data=urllib.parse.urlencode({"ptSignature":sig,"mode":"1","key":key}).encode()
        try:blob,durl,dh=request("https://m.koat.or.kr/download.do",data,referer=url)
        except Exception as e:
          print("DLERR",key,si,type(e).__name__,e);continue
        print("DL",key,si,len(blob),durl,dh.get("content-type"),dh.get("content-disposition"),blob[:8])
        if blob.startswith(b"PK\x03\x04"):
          inspect_xlsx(blob);ok=True;break
        if blob.startswith(b"%PDF"):
          print("PDF_OK");ok=True;break
      if ok: break
