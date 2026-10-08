#!/usr/bin/env python3
from __future__ import annotations
import io,urllib.request
from pypdf import PdfReader
URL="https://www.fira.or.kr/_custom/cms/_common/board/fira.jsp?attach_no=36477"
UA="Mozilla/5.0"
req=urllib.request.Request(URL,headers={"User-Agent":UA})
with urllib.request.urlopen(req,timeout=20) as r: blob=r.read()
reader=PdfReader(io.BytesIO(blob))
for i,p in enumerate(reader.pages):
    print("\nPAGE",i+1)
    try: txt=p.extract_text(extraction_mode="layout") or ""
    except Exception: txt=p.extract_text() or ""
    for n,line in enumerate(txt.splitlines(),1):
        if line.strip(): print(n,repr(line))
