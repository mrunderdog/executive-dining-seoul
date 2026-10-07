#!/usr/bin/env python3
import urllib.request,io
from pypdf import PdfReader
URL="https://www.khug.or.kr/khugcms/board/skin/download.jsp?id=1036&fileId=28358"
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.khug.or.kr/openapi/web/go/th/goth000003.jsp?id=1035&subCategory=20841"})
with urllib.request.urlopen(req,timeout=20) as r: blob=r.read()
print("BYTES",len(blob),"MAGIC",blob[:5])
pdf=PdfReader(io.BytesIO(blob))
print("PAGES",len(pdf.pages))
for i,p in enumerate(pdf.pages[:6]):
    text=p.extract_text(extraction_mode="layout") or ""
    print("PAGE",i+1)
    for line in text.splitlines()[:120]:print("TXT",repr(line))
