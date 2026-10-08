#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://www.khidi.or.kr/board/view?boardStyle=&categoryId=&continent=&country=&linkId=48949538&maxIndex=00489495389998&menuId=MENU01440&minIndex=00487154929998&no1=255&pageNum=1&rowCnt=10&schText=&schType=0&upDown=0"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read();enc=r.headers.get_content_charset() or "utf-8"
    print("STATUS",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
needle="임원업무추진비내역(2026년8월).xlsx"
i=doc.find(needle)
print("IDX",i)
if i>=0: print(html.unescape(doc[max(0,i-5000):i+8000]))
for m in re.finditer(r"<a\b[^>]*(?:href|onclick)=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>",doc,re.I|re.S):
    attr=html.unescape(m.group(1))
    txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    if any(k in (txt+" "+attr).lower() for k in (".xlsx",".xls","download","첨부")):
        print("LINK",txt,attr[:2000])
