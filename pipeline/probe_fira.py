#!/usr/bin/env python3
from __future__ import annotations
import io,urllib.request
from pypdf import PdfReader

URL="https://www.fira.or.kr/_custom/cms/_common/board/fira.jsp?attach_no=36477"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Referer":"https://www.fira.or.kr/newfira/web/info/info02_02.jsp?article_no=35818&board_no=186&mode=view"})
with urllib.request.urlopen(req,timeout=20) as r:
    blob=r.read()
    print("DOWNLOAD",len(blob),r.geturl(),r.headers.get("content-type"),r.headers.get("content-disposition"),blob[:8])
reader=PdfReader(io.BytesIO(blob))
print("PAGES",len(reader.pages))
for i,p in enumerate(reader.pages[:6]):
    txt=p.extract_text() or ""
    print("\nPAGE",i+1,"\n",txt[:12000])
