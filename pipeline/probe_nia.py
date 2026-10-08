#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request
URL="https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=24254"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read();enc=r.headers.get_content_charset() or "utf-8"
    print("STATUS",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
needle="2026년 8월 임원(기관장 제외) 업무추진비"
i=doc.find(needle)
print("FOUND",i)
if i>=0:
    print("CONTEXT\n",html.unescape(doc[max(0,i-5000):i+8000]))
for pat in [r"view([^)]*)",r"fn_[A-Za-z0-9_]+([^)]*)",r"bbsView[^\s'\"]*"]:
    print("\nPAT",pat)
    for m in re.finditer(pat,doc,re.I):
        s=html.unescape(m.group(0))
        if "24254" in s or "view" in s.lower():
            print(s[:1000])
