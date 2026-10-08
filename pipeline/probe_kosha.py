#!/usr/bin/env python3
from __future__ import annotations
import re,urllib.request

URL="https://www.kosha.or.kr/stdtboard/js/kosha-tboard-common.js"
UA="Mozilla/5.0"
req=urllib.request.Request(URL,headers={"User-Agent":UA})
with urllib.request.urlopen(req,timeout=20) as r:
    s=r.read().decode("utf-8","replace")
print("LEN",len(s))
for pat in ["fileDownloadAll","fileDownList","fileDownload.do","bbsAtcflNo","downloadFile","fileNm"]:
    print("\n###",pat)
    for m in list(re.finditer(re.escape(pat),s,re.I))[:12]:
        print(s[max(0,m.start()-2500):m.start()+6500])
