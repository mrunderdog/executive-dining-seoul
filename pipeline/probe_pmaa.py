#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://www.pmaa.or.kr/www/1461128776985/bbs.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
data=urllib.parse.urlencode({"type":"view","bbsIdx":"42469"}).encode()
req=urllib.request.Request(URL,data=data,headers={
    "User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9",
    "Content-Type":"application/x-www-form-urlencoded","Referer":URL,
})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read();enc=r.headers.get_content_charset() or "utf-8"
    print("STATUS",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
needle="2026년 8월_임원_업무추진비_사용내역.pdf"
i=doc.find(needle)
print("IDX",i)
print(html.unescape(doc[max(0,i-5000):i+8000]) if i>=0 else "not found")
for pat in [r"function\s+fn_[A-Za-z0-9_]*down[A-Za-z0-9_]*\s*\([^)]*\)\s*\{.*?\}",
            r"function\s+fn_[A-Za-z0-9_]*file[A-Za-z0-9_]*\s*\([^)]*\)\s*\{.*?\}"]:
    for m in re.finditer(pat,doc,re.I|re.S):
        print("DEF",html.unescape(m.group(0))[:8000])
