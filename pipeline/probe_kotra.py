#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://www.kotra.or.kr/kotra/module/beffatPlbc/selectBeffatPlbcUsrListItemAjax.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9","Referer":"https://www.kotra.or.kr/kp/subList/20000005799"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); enc=r.headers.get_content_charset() or "utf-8"
    print("PAGE",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
for needle in ["임원(기관장 제외) 업무추진비성 경비 사용내역","부서장 업무추진비성 경비 사용내역"]:
    i=doc.find(needle)
    print("\nNEEDLE",needle,"IDX",i)
    if i>=0: print(html.unescape(doc[max(0,i-5000):i+10000]))
