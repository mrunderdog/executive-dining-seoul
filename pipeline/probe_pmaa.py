#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://www.pmaa.or.kr/www/1461128776985/bbs.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
data=urllib.parse.urlencode({"type":"view","bbsIdx":"42469"}).encode()
req=urllib.request.Request(URL,data=data,headers={
    "User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9",
    "Content-Type":"application/x-www-form-urlencoded","Referer":URL,
})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read();enc=r.headers.get_content_charset() or "utf-8"
doc=raw.decode(enc,"replace")
for pat in [r"function\s+fn_www_download2\s*\([^)]*\)\s*\{.*?\}",r"fn_www_download2\s*=\s*function\s*\([^)]*\)\s*\{.*?\}"]:
    for m in re.finditer(pat,doc,re.I|re.S):
        print("DEF",html.unescape(m.group(0))[:8000])
for m in re.finditer(r"<script\b[^>]*src=['\"]([^'\"]+)['\"]",doc,re.I):
    src=urllib.parse.urljoin(URL,html.unescape(m.group(1)))
    try:
        rq=urllib.request.Request(src,headers={"User-Agent":UA,"Referer":URL})
        with urllib.request.urlopen(rq,timeout=20) as r:
            s=r.read().decode(r.headers.get_content_charset() or "utf-8","replace")
        if "fn_www_download2" in s:
            i=s.find("fn_www_download2")
            print("SCRIPT",src)
            print(s[max(0,i-3000):i+7000])
    except Exception:
        pass
