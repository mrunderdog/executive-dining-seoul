#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request
URL="https://www.kotra.or.kr/kp/subList/20000005799"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); enc=r.headers.get_content_charset() or "utf-8"
doc=raw.decode(enc,"replace")
print("PAGE",len(raw))
for needle in ("fnSubBplbcListToggle","selectBeffatPlbcUsrListItemAjax"):
    i=doc.find(needle); print("INLINE",needle,i)
    if i>=0: print(html.unescape(doc[max(0,i-4000):i+8000]))
print("SCRIPTS")
for m in re.finditer(r"<script\\b[^>]*src=['\\\"]([^'\\\"]+)['\\\"]",doc,re.I):
    print(urllib.parse.urljoin(URL,html.unescape(m.group(1))))
