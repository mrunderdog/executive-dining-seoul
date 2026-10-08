#!/usr/bin/env python3
from __future__ import annotations
import io,urllib.request
import pdfplumber

URL="https://www.hrdkorea.or.kr/cms/download/downloadFile.hrd?attachSeq=2053342"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Referer":"https://www.hrdkorea.or.kr/7/5/5/10/2?k=56019"})
with urllib.request.urlopen(req,timeout=20) as r:
    blob=r.read()
    print("DOWNLOAD",len(blob),r.geturl(),r.headers.get("content-type"),r.headers.get("content-disposition"),blob[:8])
with pdfplumber.open(io.BytesIO(blob)) as pdf:
    print("PAGES",len(pdf.pages))
    for i,p in enumerate(pdf.pages,1):
        print("\nPAGE",i)
        tabs=p.extract_tables()
        print("TABLES",len(tabs))
        for ti,t in enumerate(tabs,1):
            print("TABLE",ti)
            for row in t[:30]:
                print(repr(row))
