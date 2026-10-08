#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

BASE="https://www.nia.or.kr"
LIST="https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=24254"
DETAIL=BASE+"/site/nia_kor/ex/bbs/View.do?cbIdx=24254&bcIdx=30021&parentSeq=30021"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def get(url,referer=LIST):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9","Referer":referer})
    with urllib.request.urlopen(req,timeout=20) as r:
        raw=r.read(); enc=r.headers.get_content_charset() or "utf-8"
        print("GET",len(raw),r.geturl(),r.headers.get("content-type"))
        return raw.decode(enc,"replace")

doc=get(DETAIL)
for m in re.finditer(r"<a\b[^>]*href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>",doc,re.I|re.S):
    href=html.unescape(m.group(1))
    txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    if any(k in (txt+" "+href).lower() for k in ("첨부","download",".xlsx",".xls",".pdf",".hwp")):
        print("LINK",txt,urllib.parse.urljoin(DETAIL,href))
for pat in [r"fileDown[^\n<]{0,500}",r"download[^\n<]{0,500}",r"atch[^\n<]{0,500}"]:
    for m in re.finditer(pat,doc,re.I):
        print("PAT",html.unescape(m.group(0))[:1000])
