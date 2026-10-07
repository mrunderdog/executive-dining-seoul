#!/usr/bin/env python3
from __future__ import annotations
import re,urllib.request,time
URLS=[
 "https://www.kibo.or.kr/js/gfn_file.js?1612277966000",
 "https://www.kibo.or.kr/_custom/kibo/resource/js/board.common.js?1657689800000",
 "https://www.kibo.or.kr/_res/_common/js/cms.js",
]
UA="Mozilla/5.0"
for URL in URLS:
    print("\nURL",URL)
    last=None
    for i in range(3):
        try:
            req=urllib.request.Request(URL,headers={"User-Agent":UA,"Referer":"https://www.kibo.or.kr/main/board/boardType46.do?mode=list"})
            with urllib.request.urlopen(req,timeout=15) as r:
                s=r.read().decode(r.headers.get_content_charset() or "utf-8","replace")
            break
        except Exception as e:
            last=e; print("RETRY",i+1,type(e).__name__,e); time.sleep(i+1)
    else: raise last
    for needle in ("file-down-btn","data-file-id","data-file-key","download","attach"):
        pos=0
        while True:
            j=s.lower().find(needle.lower(),pos)
            if j<0:break
            print("\n",needle,"\n",s[max(0,j-1200):j+2800])
            pos=j+len(needle)
