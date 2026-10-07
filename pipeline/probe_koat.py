#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URLS=[
  "https://m.koat.or.kr/board/expenseInst/list.do",
  "https://m.koat.or.kr/board/expenseExec/list.do",
]
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req,timeout=20) as r:
        raw=r.read()
        return raw.decode(r.headers.get_content_charset() or "utf-8","replace"),r.geturl(),r.headers

for url in URLS:
    print("\nURL",url)
    try: doc,final,h=fetch(url)
    except Exception as e:
        print("ERR",type(e).__name__,e); continue
    print("STATUS",len(doc),final,h.get("content-type"))
    for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
        txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
        if "2026년 9월" in txt or "2026년 8월" in txt:
            print("ROW",html.unescape(row)[:8000])
    for m in re.finditer(r"(?:href|onclick)\s*=\s*['\"][^'\"]+['\"]",doc,re.I):
        s=html.unescape(m.group(0))
        if any(k in s.lower() for k in ("view.do","file","down","expense")) and ("2026" in s or "view.do" in s):
            print("LINK",s[:1200])
