#!/usr/bin/env python3
from __future__ import annotations
import urllib.request,time

URL="https://www.kibo.or.kr/_custom/kibo/resource/js/board.listDownload.js?1609553316000"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
last=None
for i in range(3):
    try:
        req=urllib.request.Request(URL,headers={"User-Agent":UA,"Referer":"https://www.kibo.or.kr/main/board/boardType46.do?mode=list"})
        with urllib.request.urlopen(req,timeout=15) as r:
            raw=r.read()
            print(raw.decode(r.headers.get_content_charset() or "utf-8","replace"))
            break
    except Exception as e:
        last=e; print("RETRY",i+1,type(e).__name__,e); time.sleep(i+1)
else:
    raise last
