#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://www.kobc.or.kr/ebz/kor/bbs/view.do?bIdx=98052&mId=0601020400&ptIdx=341"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); enc=r.headers.get_content_charset() or "utf-8"
    print("STATUS",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
for m in re.finditer(r"<a\b[^>]*href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>",doc,re.I|re.S):
    href=html.unescape(m.group(1))
    txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    if ".pdf" in txt.lower() or "download" in href.lower() or "file" in href.lower():
        print("LINK",txt,urllib.parse.urljoin(URL,href))
