#!/usr/bin/env python3
from __future__ import annotations
import io,urllib.request
from pypdf import PdfReader
UA="Mozilla/5.0"

def get(url,referer=""):
 h={"User-Agent":UA}
 if referer:h["Referer"]=referer
 req=urllib.request.Request(url,headers=h)
 with urllib.request.urlopen(req,timeout=30) as r:return r.read()

for name,url in [
 ("FIRA","https://www.fira.or.kr/_custom/cms/_common/board/fira.jsp?attach_no=36135"),
 ("NILE","https://www.nile.or.kr/usr/wap/downloadFile.do?app=12716&seq=2196347&atchFileSeq=2196345&fileColumn=atchFileSeq&fileSn=0&lang=ko"),
]:
 blob=get(url)
 print("\n====",name,"====")
 for pi,p in enumerate(PdfReader(io.BytesIO(blob)).pages):
  try:t=p.extract_text(extraction_mode="layout") or ""
  except Exception:t=p.extract_text() or ""
  print("PAGE",pi+1)
  for line in t.splitlines()[:120]:
   print(repr(line))
