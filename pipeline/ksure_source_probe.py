#!/usr/bin/env python3
import io,re,html,zipfile,urllib.parse,urllib.request,xml.etree.ElementTree as ET
LIST="https://www.ksure.or.kr/rh-kr/bbs/i-480/list.do"
UA="Mozilla/5.0"
NS={"a":"http://schemas.openxmlformats.org/spreadsheetml/2006/main","r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
def fetch(url,ref=""):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Referer":ref or LIST,"Accept-Language":"ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req,timeout=15) as r:return r.read(),r.headers.get_content_charset()
raw,cs=fetch(LIST);doc=raw.decode(cs or "utf-8",errors="replace")
for block in re.findall(r"<li\b.*?</li>|<tr\b.*?</tr>",doc,re.I|re.S):
    text=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",block)).split())
    dm=re.search(r'href=["\']([^"\']*down\.do\?[^"\']+)["\']',block,re.I)
    if dm and "2026년" in text:
        print("ITEM",text[:300],urllib.parse.urljoin(LIST,html.unescape(dm.group(1))))
def xrows(blob):
    z=zipfile.ZipFile(io.BytesIO(blob));shared=[]
    if "xl/sharedStrings.xml" in z.namelist():
        root=ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("a:si",NS):shared.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
    wb=ET.fromstring(z.read("xl/workbook.xml"));rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap={r.attrib["Id"]:r.attrib["Target"] for r in rels}
    for sh in wb.find("a:sheets",NS):
        name=sh.attrib.get("name","");rid=sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id","");target=relmap.get(rid,"")
        path=target if target.startswith("xl/") else "xl/"+target.lstrip("/")
        if path not in z.namelist():path="xl/"+target.replace("../","").lstrip("/")
        print("SHEET",name)
        root=ET.fromstring(z.read(path))
        for row in root.findall(".//a:sheetData/a:row",NS)[:25]:
            vals=[]
            for c in row.findall("a:c",NS):
                typ=c.attrib.get("t","");v=c.find("a:v",NS);val="" if v is None else (v.text or "")
                if typ=="s" and val.isdigit() and int(val)<len(shared):val=shared[int(val)]
                elif typ=="inlineStr":val="".join(t.text or "" for t in c.iter() if t.tag.endswith("}t"))
                vals.append(f"{c.attrib.get('r','')}={val}")
            print("ROW",row.attrib.get("r")," | ".join(vals))
for n in (233,234,235):
    u=f"https://www.ksure.or.kr/rh-kr/bbs/i-480/down.do?bbs_id=1049&ntt_sn={n}&data_ty_cd=A&atfile_sn=1"
    blob,_=fetch(u,LIST)
    print("FILE",n,"BYTES",len(blob),"MAGIC",blob[:4])
    xrows(blob)
