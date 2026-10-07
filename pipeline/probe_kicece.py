#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.request

URL="https://www.kicece.or.kr/kcpi/openmag/bzexpenseDetail.do?year=202607"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); enc=r.headers.get_content_charset() or "utf-8"
    print("STATUS",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
    txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
    if re.search(r"2026[-./]0?7[-./]\d{1,2}",txt) or any(x in txt for x in ("사용일자","집행내역","사용처","집행대상자","집행금액")):
        print("ROW",txt)
