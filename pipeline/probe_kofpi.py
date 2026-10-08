#!/usr/bin/env python3
from __future__ import annotations
import io,urllib.parse,urllib.request
import xlrd
URL="https://www.kofpi.or.kr/noti/download.do"
REF="https://www.kofpi.or.kr/public/publicInfo_03_001view.do"
UA="Mozilla/5.0"
data=urllib.parse.urlencode({"fileSeq":"15654"}).encode()
req=urllib.request.Request(URL,data=data,headers={"User-Agent":UA,"Referer":REF,"Content-Type":"application/x-www-form-urlencoded"})
with urllib.request.urlopen(req,timeout=20) as r: blob=r.read()
book=xlrd.open_workbook(file_contents=blob)
print("SHEETS",book.sheet_names())
for si in range(book.nsheets):
    sh=book.sheet_by_index(si)
    print("\nSHEET",si,sh.name,sh.nrows,sh.ncols)
    for ri in range(min(sh.nrows,40)):
        vals=[" ".join(str(sh.cell_value(ri,ci) or "").split()) for ci in range(sh.ncols)]
        if any(v for v in vals):
            print(ri,vals)
