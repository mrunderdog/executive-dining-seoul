#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://www.keco.or.kr/web/lay1/bbs/S1T106C997/A/52/view.do?article_seq=100583&condition=&cpage=1&keyword=&rows=10"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); enc=r.headers.get_content_charset() or "utf-8"
    print("PAGE",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
for m in re.finditer(r"<a\b[^>]*(?:href|onclick)=['\"][^'\"]+['\"][^>]*>.*?</a>",doc,re.I|re.S):
    s=html.unescape(m.group(0))
    txt=" ".join(re.sub(r"<[^>]+>"," ",s).split())
    if ".xls" in s.lower() or "download" in s.lower() or "file" in s.lower():
        print("A",s[:4000])
