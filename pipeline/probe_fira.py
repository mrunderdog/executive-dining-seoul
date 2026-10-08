#!/usr/bin/env python3
from __future__ import annotations
import io,urllib.request
import pdfplumber
URL="https://www.fira.or.kr/_custom/cms/_common/board/fira.jsp?attach_no=36477"
UA="Mozilla/5.0"
req=urllib.request.Request(URL,headers={"User-Agent":UA})
with urllib.request.urlopen(req,timeout=20) as r: blob=r.read()
with pdfplumber.open(io.BytesIO(blob)) as pdf:
    for i,p in enumerate(pdf.pages,1):
        print("\nPAGE",i)
        tables=p.extract_tables()
        print("TABLES",len(tables))
        for ti,t in enumerate(tables,1):
            print("TABLE",ti)
            for row in t:
                print(repr(row))
