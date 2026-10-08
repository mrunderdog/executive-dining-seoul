#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://www.pmaa.or.kr/www/1461128776985/bbs.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
data=urllib.parse.urlencode({"type":"view","bbsIdx":"42469"}).encode()
req=urllib.request.Request(URL,data=data,headers={
    "User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9",
    "Content-Type":"application/x-www-form-urlencoded","Referer":URL,
})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read();enc=r.headers.get_content_charset() or "utf-8"
    print("STATUS",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
print("TITLE_FOUND", "2026년 8월 임원업무추진비 사용 내역" in doc)
for m in re.finditer(r"<a\b[^>]*(?:href|onclick)=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>",doc,re.I|re.S):
    attr=html.unescape(m.group(1))
    txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    blob=(txt+" "+attr).lower()
    if any(k in blob for k in ("첨부","download",".xlsx",".xls",".pdf",".hwp")):
        print("LINK",txt,attr[:2000])
for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
    txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
    if any(k in txt for k in ("사용일자","사용처","집행금액","사용금액")):
        print("ROW",txt)
