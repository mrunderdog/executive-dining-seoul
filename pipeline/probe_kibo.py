#!/usr/bin/env python3
from __future__ import annotations
import html,re,time,urllib.parse,urllib.request

URL="https://www.kibo.or.kr/main/board/boardType46.do?article.offset=0&mode=list"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def fetch(url):
    last=None
    for i in range(4):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9","Referer":URL})
            with urllib.request.urlopen(req,timeout=20) as r:
                raw=r.read()
                return raw.decode(r.headers.get_content_charset() or "utf-8","replace"),r.geturl(),r.headers
        except Exception as e:
            last=e; print("RETRY",i+1,type(e).__name__,e); time.sleep(2*(i+1))
    raise last

doc,final,h=fetch(URL)
print("STATUS",len(doc),final)
for m in re.finditer(r"<script\b[^>]*src=['\"]([^'\"]+)['\"]",doc,re.I):
    src=urllib.parse.urljoin(URL,html.unescape(m.group(1)))
    try:s,_,_=fetch(src)
    except Exception:continue
    if "file-down-btn" in s or "data-file-id" in s or "data-file-key" in s:
        print("\nSCRIPT",src)
        for needle in ("file-down-btn","data-file-id","data-file-key"):
            i=s.find(needle)
            if i>=0: print(s[max(0,i-3500):i+7000])

print("\nLATEST FILES")
for m in re.finditer(r'<a\b([^>]*class=["\'][^"\']*file-down-btn[^"\']*["\'][^>]*)>(.*?)</a>',doc,re.I|re.S):
    attrs=m.group(1);name=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    if "2026년" not in name:continue
    def a(k):
        mm=re.search(rf'data-{k}=["\']([^"\']+)["\']',attrs,re.I)
        return mm.group(1) if mm else ""
    print(name,{"file-id":a("file-id"),"file-vl":a("file-vl"),"file-key":a("file-key")})
