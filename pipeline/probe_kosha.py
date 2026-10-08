#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://www.kosha.or.kr/esg/management-disclosure/self-disclosure/executive-expenses/research-director"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); enc=r.headers.get_content_charset() or "utf-8"
    print("PAGE",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
print("\nDOC\n",doc[:12000])
print("\nSCRIPTS")
for m in re.finditer(r"<script\b[^>]*src=['\"]([^'\"]+)['\"]",doc,re.I):
    src=urllib.parse.urljoin(URL,html.unescape(m.group(1)))
    print(src)
    try:
        rr=urllib.request.Request(src,headers={"User-Agent":UA,"Referer":URL})
        with urllib.request.urlopen(rr,timeout=20) as r:
            b=r.read(); s=b.decode("utf-8","replace")
        print("SCRIPT_LEN",len(s))
        for pat in ("executive-expenses","research-director","api/","axios","fetch("):
            if pat in s:
                i=s.find(pat); print("HIT",pat,s[max(0,i-1200):i+3500])
    except Exception as e:
        print("SCRIPT_ERR",type(e).__name__,e)
