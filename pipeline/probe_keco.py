#!/usr/bin/env python3
from __future__ import annotations
import io,urllib.request
import xlrd

URL="https://www.keco.or.kr/download.do?uuid=6a5c8cdf-8314-4b11-95ac-f77b250e9158.xls"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Referer":"https://www.keco.or.kr/"})
with urllib.request.urlopen(req,timeout=20) as r:
    blob=r.read()
    print("XLS",len(blob),r.geturl(),r.headers.get("content-type"),r.headers.get("content-disposition"),blob[:8])
book=xlrd.open_workbook(file_contents=blob)
for si in range(book.nsheets):
    sh=book.sheet_by_index(si)
    print("SHEET",si,sh.name,sh.nrows,sh.ncols)
    for ri in range(min(30,sh.nrows)):
        vals=[" ".join(str(sh.cell_value(ri,ci)).split()) for ci in range(sh.ncols)]
        print(ri+1,vals)
