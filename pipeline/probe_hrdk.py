#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://www.hrdkorea.or.kr/7/5/5/10/2?k=56019&pageNo=&searchType=&searchText="
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); enc=r.headers.get_content_charset() or "euc-kr"
    print("STATUS",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
for m in re.finditer(r"<a\b[^>]*href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>",doc,re.I|re.S):
    href=html.unescape(m.group(1))
    txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    if any(k in (txt+href).lower() for k in (".pdf",".xlsx",".xls","down","file","attach")):
        print("LINK",txt,urllib.parse.urljoin(URL,href))
for m in re.finditer(r"(?:onclick|href)\s*=\s*['\"][^'\"]+['\"]",doc,re.I):
    s=html.unescape(m.group(0))
    if any(k in s.lower() for k in ("file","down","attach")):
        print("ATTR",s[:1000])
