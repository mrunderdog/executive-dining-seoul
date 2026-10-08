#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request
URL="https://www.pmaa.or.kr/www/1461128776985/bbs.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read();enc=r.headers.get_content_charset() or "utf-8"
    print("STATUS",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
for m in re.finditer(r"<form\b[^>]*name=['\"]frm_list['\"][^>]*>",doc,re.I):
    print("FORM",html.unescape(m.group(0)))
