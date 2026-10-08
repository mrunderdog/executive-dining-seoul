#!/usr/bin/env python3
from __future__ import annotations
import urllib.parse,urllib.request
BASE="https://www.fowi.or.kr"
REF=BASE+"/user/publication/coreView.do?coreId=22&menu=core_"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
url=BASE+"/selectGenerateDownloadLink.do?"+urllib.parse.urlencode({"fileId":"30857"})
req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"*/*","Referer":REF,"X-Requested-With":"XMLHttpRequest"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read()
    print("LINK_RESPONSE",len(raw),r.geturl(),r.headers.get("content-type"),raw[:3000].decode(r.headers.get_content_charset() or "utf-8","replace"))
