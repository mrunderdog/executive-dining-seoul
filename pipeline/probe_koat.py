#!/usr/bin/env python3
from __future__ import annotations
import html,urllib.request

URL="https://m.koat.or.kr/board/expenseInst/list.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); enc=r.headers.get_content_charset() or "utf-8"
    print("LIST",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
i=doc.find("function fn_borad_file_down")
print("FUNC_INDEX",i)
print(html.unescape(doc[i:i+5000]) if i>=0 else "NOT_FOUND")
