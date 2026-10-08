#!/usr/bin/env python3
from __future__ import annotations
import io,urllib.request
from pypdf import PdfReader

URL="https://www.fira.or.kr/fira/_files/2026/09/30/a7988f07b7f5c15dfba462e0c1c2defd.pdf"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Referer":"https://www.fira.or.kr/"})
with urllib.request.urlopen(req,timeout=20) as r:
    blob=r.read()
    print("PDF",len(blob),r.geturl(),r.headers.get("content-type"),blob[:8])
reader=PdfReader(io.BytesIO(blob))
print("PAGES",len(reader.pages))
for i,p in enumerate(reader.pages[:10]):
    txt=p.extract_text() or ""
    print("\nPAGE",i+1,"\n",txt[:12000])
