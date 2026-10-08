#!/usr/bin/env python3
from __future__ import annotations
import re,urllib.request

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
BASE="https://www.kosha.or.kr"
URL=BASE+"/stdtboard/js/kosha-tboard-interface.js"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Referer":BASE+"/esg/management-disclosure/self-disclosure/executive-expenses/research-director"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); s=raw.decode("utf-8","replace")
print("INTERFACE",len(s),r.geturl(),r.headers.get("content-type"))
for pat in [
    "process.do","api.do","fileDownload.do","boardId","boardNo","boardSeq",
    "list","search","selectList","selectBoard","getList","bbs","tboard"
]:
    print("\n###",pat)
    seen=0
    for m in re.finditer(re.escape(pat),s,re.I):
        print(s[max(0,m.start()-1200):m.start()+3200])
        seen+=1
        if seen>=3:break

# Also inspect the main Vue bundle for the route and lazy component around it.
MAIN=BASE+"/static/js/index-CTxvCDqC.js"
req=urllib.request.Request(MAIN,headers={"User-Agent":UA})
with urllib.request.urlopen(req,timeout=20) as r:
    ms=r.read().decode("utf-8","replace")
print("\nMAIN",len(ms))
for pat in ["executive-expenses","research-director","tech-director","self-disclosure"]:
    print("\nROUTE",pat)
    for m in list(re.finditer(re.escape(pat),ms,re.I))[:5]:
        print(ms[max(0,m.start()-1800):m.start()+3800])
