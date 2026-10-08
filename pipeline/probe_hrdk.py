#!/usr/bin/env python3
from __future__ import annotations
import urllib.request

IDS=["2050908","2051109","2051470","2051804","2052107","2052299","2053038","2052972","2053342"]
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
for aid in IDS:
    url=f"https://www.hrdkorea.or.kr/cms/download/downloadFile.hrd?attachSeq={aid}"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA})
        with urllib.request.urlopen(req,timeout=20) as r:
            blob=r.read()
            print(aid,len(blob),r.headers.get("content-type"),r.headers.get("content-disposition"),repr(blob[:16]))
    except Exception as e:
        print(aid,"ERR",type(e).__name__,e)
