#!/usr/bin/env python3
from __future__ import annotations
import io,re,urllib.request,zipfile,xml.etree.ElementTree as ET

URL="https://www.nia.or.kr/common/board/Download.do?bcIdx=30021&cbIdx=24254&fileNo=1"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Referer":"https://www.nia.or.kr/site/nia_kor/ex/bbs/View.do?cbIdx=24254&bcIdx=30021&parentSeq=30021"})
with urllib.request.urlopen(req,timeout=20) as r:
    blob=r.read()
    print("DOWNLOAD",len(blob),r.geturl(),r.headers.get("content-type"),r.headers.get("content-disposition"),blob[:8])

z=zipfile.ZipFile(io.BytesIO(blob))
print("FILES",z.namelist()[:50])
for name in z.namelist():
    if not (name.startswith("Contents/section") and name.endswith(".xml")): continue
    raw=z.read(name)
    root=ET.fromstring(raw)
    texts=[]
    for el in root.iter():
        if el.text and el.text.strip():
            texts.append(" ".join(el.text.split()))
    print("\nSECTION",name)
    print("\n".join(texts[:500]))
