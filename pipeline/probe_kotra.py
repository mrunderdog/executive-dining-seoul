#!/usr/bin/env python3
from __future__ import annotations
import urllib.request
BASE="https://www.kotra.or.kr"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
paths=[
 "/js/wzwg/screen/usrScreen.js",
 "/js/wzwg/site/siteWizbuilder.js",
 "/js/wzwg/cmm/common.js",
 "/js/kotra/cmm/kotraMember.js",
]
for p in paths:
    url=BASE+p
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA,"Referer":BASE+"/kp/subList/20000005799"})
        with urllib.request.urlopen(req,timeout=15) as r:
            s=r.read().decode(r.headers.get_content_charset() or "utf-8","replace")
        print("\nSCRIPT",url,"LEN",len(s))
        for needle in ("fnSubBplbcListToggle","selectBeffatPlbcUsr","beffatPlbc"):
            i=s.find(needle)
            if i>=0:
                print("FOUND",needle,i)
                print(s[max(0,i-6000):i+12000])
    except Exception as e:
        print("ERR",url,type(e).__name__,e)
