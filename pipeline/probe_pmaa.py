#!/usr/bin/env python3
from __future__ import annotations
import io,urllib.parse,urllib.request
from pypdf import PdfReader

URL="https://www.pmaa.or.kr/fileDownload.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
data=urllib.parse.urlencode({
    "path":"NOTICE",
    "physicalName":"6308dfc4-70b9-43b5-8a1a-b898142b7d22.pdf",
    "original":"2026년 8월_임원_업무추진비_사용내역.pdf"
}).encode()
req=urllib.request.Request(URL,data=data,headers={
    "User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded",
    "Referer":"https://www.pmaa.or.kr/www/1461128776985/bbs.do"
})
with urllib.request.urlopen(req,timeout=20) as r:
    blob=r.read()
    print("DOWNLOAD",len(blob),r.geturl(),r.headers.get("content-type"),r.headers.get("content-disposition"),blob[:8])
reader=PdfReader(io.BytesIO(blob))
print("PAGES",len(reader.pages))
for i,p in enumerate(reader.pages[:6],1):
    try: txt=p.extract_text(extraction_mode="layout") or ""
    except Exception: txt=p.extract_text() or ""
    print("\nPAGE",i,"\n",txt[:16000])
