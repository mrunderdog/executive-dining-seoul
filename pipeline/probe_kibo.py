#!/usr/bin/env python3
from __future__ import annotations
import html,re,time,urllib.parse,urllib.request

URL="https://www.kibo.or.kr/main/board/boardType46.do?article.offset=0&mode=list"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def fetch(url):
    last=None
    for i in range(4):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
            with urllib.request.urlopen(req,timeout=20) as r:
                raw=r.read()
                return raw.decode(r.headers.get_content_charset() or "utf-8","replace"),r.geturl(),r.headers
        except Exception as e:
            last=e; print("RETRY",i+1,type(e).__name__,e); time.sleep(2*(i+1))
    raise last

doc,final,h=fetch(URL)
print("STATUS",len(doc),final,h.get("content-type"))
for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
    txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
    if "2026년 6월" in txt or "2026년 5월" in txt:
        print("\nROW\n",html.unescape(row)[:10000])
for m in re.finditer(r"(?:href|onclick)\s*=\s*['\"][^'\"]+['\"]",doc,re.I):
    s=html.unescape(m.group(0))
    if any(k in s.lower() for k in ("attach","file","down","article")):
        print("HOOK",s[:1500])
