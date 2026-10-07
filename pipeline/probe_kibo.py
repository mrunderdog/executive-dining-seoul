#!/usr/bin/env python3
from __future__ import annotations
import html,re,time,urllib.parse,urllib.request

URL="https://www.kibo.or.kr/main/board/boardType46.do?article.offset=0&mode=list"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def fetch(url):
    last=None
    for i in range(3):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9","Referer":URL})
            with urllib.request.urlopen(req,timeout=15) as r:
                raw=r.read()
                return raw.decode(r.headers.get_content_charset() or "utf-8","replace"),r.geturl(),r.headers
        except Exception as e:
            last=e; print("RETRY",i+1,type(e).__name__,e); time.sleep(i+1)
    raise last

doc,final,h=fetch(URL)
print("STATUS",len(doc),final)
print("SCRIPTS")
for m in re.finditer(r"<script\b[^>]*src=['\"]([^'\"]+)['\"]",doc,re.I):
    src=urllib.parse.urljoin(URL,html.unescape(m.group(1)))
    print(src)

print("INLINE FILE HANDLERS")
for needle in ("file-down-btn","data-file-id","data-file-key","download"):
    pos=0
    while True:
        i=doc.find(needle,pos)
        if i<0:break
        print("\nNEEDLE",needle,"\n",html.unescape(doc[max(0,i-1200):i+2500]))
        pos=i+len(needle)

print("LATEST FILES")
for m in re.finditer(r'<a\b([^>]*class=["\'][^"\']*file-down-btn[^"\']*["\'][^>]*)>(.*?)</a>',doc,re.I|re.S):
    attrs=m.group(1);name=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    if "2026년" not in name:continue
    print(name,attrs)
