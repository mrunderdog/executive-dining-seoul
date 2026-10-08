#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.request
URL="https://www.kotra.or.kr/kp/subList/20000005799"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); enc=r.headers.get_content_charset() or "utf-8"
doc=raw.decode(enc,"replace")
print("PAGE",len(raw))
seen=set()
for m in re.finditer(r"[^\"'<>\s]{0,80}(?:beffatPlbc|Bplbc|bplbc|Plbc)[^\"'<>\s]{0,180}",doc,re.I):
    s=html.unescape(m.group(0))
    if s not in seen:
        seen.add(s); print("HIT",s)
for m in re.finditer(r"<form\b[^>]*>|<script\b[^>]*>",doc,re.I):
    s=html.unescape(m.group(0))
    if "src=" in s.lower() or "action=" in s.lower(): print("TAG",s[:1000])
