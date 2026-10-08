#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://main.kotsa.or.kr/portal/bbs/finninfo_list.do?cateCode=10&menuCode=03020300&pageNumb=1"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); enc=r.headers.get_content_charset() or "utf-8"
doc=raw.decode(enc,"replace")
print("LIST",len(raw))
for pat in (r"function\s+fnView\s*\([^)]*\)\s*\{.*?\}",r"fnView\s*=\s*function\s*\([^)]*\)\s*\{.*?\}"):
    for m in re.finditer(pat,doc,re.I|re.S):
        print("DEF",html.unescape(m.group(0))[:6000])
for m in re.finditer(r"<form\b.*?</form>",doc,re.I|re.S):
    s=html.unescape(m.group(0))
    if "finninfo" in s.lower() or "bbs" in s.lower():
        print("FORM",s[:8000])
