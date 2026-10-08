#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://m.koat.or.kr/board/expenseInst/list.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def fetch(url,referer=URL):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9","Referer":referer})
    with urllib.request.urlopen(req,timeout=20) as r:
        return r.read(),r.geturl(),r.headers

raw,final,h=fetch(URL)
doc=raw.decode(h.get_content_charset() or "utf-8","replace")
print("LIST",len(raw),final,h.get("content-type"))
for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
    txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
    if "2026년 9월 기관장 업무추진비 집행내역" in txt:
        print("\nROW\n",html.unescape(row)[:10000])
for m in re.finditer(r"(?:href|onclick)\s*=\s*['\"][^'\"]+['\"]",doc,re.I):
    s=html.unescape(m.group(0))
    if any(k in s.lower() for k in ("view","detail","file","down","expenseinst")):
        print(s[:1200])
