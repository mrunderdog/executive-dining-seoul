#!/usr/bin/env python3
from __future__ import annotations
import io,urllib.request,zipfile,xml.etree.ElementTree as ET

URL="https://www.nia.or.kr/common/board/Download.do?bcIdx=30021&cbIdx=24254&fileNo=1"
UA="Mozilla/5.0"
req=urllib.request.Request(URL,headers={"User-Agent":UA})
with urllib.request.urlopen(req,timeout=20) as r: blob=r.read()
z=zipfile.ZipFile(io.BytesIO(blob))
root=ET.fromstring(z.read("Contents/section0.xml"))

def local(tag): return tag.rsplit("}",1)[-1]
for el in root.iter():
    if local(el.tag) in {"tbl","tr","tc"}:
        vals=[]
        for x in el.iter():
            if x.text and x.text.strip(): vals.append(" ".join(x.text.split()))
        print(local(el.tag),repr(" | ".join(vals[:40])))
