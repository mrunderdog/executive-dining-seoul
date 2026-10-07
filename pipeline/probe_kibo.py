#!/usr/bin/env python3
from __future__ import annotations
import urllib.request
URL="https://www.kibo.or.kr/js/gfn_file.js?1612277966000"
req=urllib.request.Request(URL,headers={
    "User-Agent":"Mozilla/5.0",
    "Referer":"https://www.kibo.or.kr/main/board/boardType46.do?mode=list",
})
with urllib.request.urlopen(req,timeout=10) as r:
    s=r.read().decode(r.headers.get_content_charset() or "utf-8","replace")
print("LEN",len(s))
i=s.find("gfn_file_download")
print(s[max(0,i-2000):i+6000] if i>=0 else s[:12000])
