#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.request
URL="https://www.kofpi.or.kr/public/publicInfo_03_001.do?sub=26"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); enc=r.headers.get_content_charset() or "utf-8"
    print("STATUS",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
for pat in (r"function\s+fnGoView\s*\([^)]*\)\s*\{.*?\}",r"function\s+fnFileDown\s*\([^)]*\)\s*\{.*?\}",r"function\s+[^\s(]*Down[^\s(]*\s*\([^)]*\)\s*\{.*?\}"):
    for m in re.finditer(pat,doc,re.I|re.S):
        print("\nFUNC\n",html.unescape(m.group(0))[:8000])
for m in re.finditer(r"<form\b.*?</form>",doc,re.I|re.S):
    s=html.unescape(m.group(0))
    if any(x in s for x in ("12673","seq","sub","view","file")):
        print("\nFORM\n",s[:8000])
