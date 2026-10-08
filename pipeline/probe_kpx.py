#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request
URL="https://www.kpx.or.kr/board.es?mid=a10202010000&bid=0023&act=view&list_no=78162"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read();enc=r.headers.get_content_charset() or "utf-8"
doc=raw.decode(enc,"replace")
for needle in [".xlsx","78162","file"]:
    i=doc.lower().find(needle.lower())
    print("\nNEEDLE",needle,"IDX",i)
    if i>=0: print(html.unescape(doc[max(0,i-5000):i+9000]))
