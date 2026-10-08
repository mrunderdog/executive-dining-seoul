#!/usr/bin/env python3
from __future__ import annotations
import html,re,ssl,urllib.request
URL="https://www.kca.go.kr/kca/sub.do?menukey=5152&mode=list&page=1"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20,context=ssl._create_unverified_context()) as r:
    doc=r.read().decode(r.headers.get_content_charset() or "utf-8","replace")
print("LEN",len(doc))
needle="2026년 8월 일자별 공개(기관장)"
i=doc.find(needle)
print("FOUND",i)
print(html.unescape(doc[max(0,i-3000):i+5000]))
