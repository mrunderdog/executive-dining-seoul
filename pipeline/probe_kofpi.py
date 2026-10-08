#!/usr/bin/env python3
from __future__ import annotations
import urllib.parse,urllib.request
URL="https://www.kofpi.or.kr/noti/download.do"
REF="https://www.kofpi.or.kr/public/publicInfo_03_001view.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
data=urllib.parse.urlencode({"fileSeq":"15654"}).encode()
req=urllib.request.Request(URL,data=data,headers={
    "User-Agent":UA,"Accept":"*/*","Accept-Language":"ko-KR,ko;q=0.9",
    "Referer":REF,"Content-Type":"application/x-www-form-urlencoded"
})
with urllib.request.urlopen(req,timeout=20) as r:
    blob=r.read()
    print("DOWNLOAD",len(blob),r.geturl(),r.headers.get("content-type"),r.headers.get("content-disposition"),blob[:16])
