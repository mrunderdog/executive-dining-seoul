#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://www.kibo.or.kr/main/board/boardType46.do?article.offset=0&mode=list"
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
    if "2026년 6월 기관장 업무추진비" in txt or "2026년 6월 임원 업무추진비" in txt:
        print("\nROW\n",html.unescape(row)[:8000])

for m in re.finditer(r"(?:href|onclick)\s*=\s*['\"][^'\"]+['\"]",doc,re.I):
    s=html.unescape(m.group(0))
    if any(k in s.lower() for k in ("file","attach","download","article","board")):
        if "2026" in s or "download" in s.lower() or "file" in s.lower():
            print(s[:1000])
