#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request
URLS=[
 "https://m.koat.or.kr/board/expenseInst/list.do",
 "https://m.koat.or.kr/board/expenseExecutive/list.do",
]
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req,timeout=20) as r:
        raw=r.read(); return raw.decode(r.headers.get_content_charset() or "utf-8","replace"),r.geturl(),r.headers
for URL in URLS:
    print("\nURL",URL)
    doc,final,h=fetch(URL); print("STATUS",len(doc),final)
    i=doc.find("function fn_borad_file_down")
    if i<0:i=doc.find("fn_borad_file_down")
    print("HOOK",html.unescape(doc[max(0,i-1000):i+5000]) if i>=0 else "NOT_FOUND")
    for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
        txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
        if "2026년 9월" in txt or "2026년 8월" in txt:
            print("ROW",html.unescape(row)[:5000])
