#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request
URL="https://www.fowi.or.kr/user/publication/coreView.do?coreId=22&menu=core_"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read();enc=r.headers.get_content_charset() or "utf-8"
    print("STATUS",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
for m in re.finditer(r"<a\b[^>]*(?:href|onclick)=['\"]([^'\"]*)['\"][^>]*>(.*?)</a>",doc,re.I|re.S):
    full=html.unescape(m.group(0)); txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    if "2026년도" in txt and ("업무추진비" in txt or ".xlsx" in txt):
        print("\nA",full[:6000])
for pat in (r"function\s+[^\s(]*(?:down|file)[^\s(]*\s*\([^)]*\)\s*\{.*?\}",):
    for m in re.finditer(pat,doc,re.I|re.S):
        print("\nFUNC\n",html.unescape(m.group(0))[:8000])

for pat in (r"function\s+fn_generateLink\s*\([^)]*\)\s*\{.*?\}",):
    for m in re.finditer(pat,doc,re.I|re.S):
        print("\nGENLINK\n",html.unescape(m.group(0))[:8000])
for m in re.finditer(r"<script\b[^>]*src=['\"]([^'\"]+)['\"]",doc,re.I):
    src=urllib.parse.urljoin(URL,html.unescape(m.group(1)))
    try:
        req=urllib.request.Request(src,headers={"User-Agent":UA,"Referer":URL})
        with urllib.request.urlopen(req,timeout=20) as r:
            js=r.read().decode(r.headers.get_content_charset() or "utf-8","replace")
        if "fn_generateLink" in js:
            i=js.find("fn_generateLink")
            print("\nSCRIPT_GENLINK",src,"\n",js[max(0,i-3000):i+7000])
    except Exception:
        pass
