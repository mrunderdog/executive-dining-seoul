#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://www.hrdkorea.or.kr/7/5/5/10/2"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req,timeout=20) as r:
        raw=r.read()
        return raw.decode(r.headers.get_content_charset() or "utf-8","replace"),r.geturl(),r.headers

doc,final,h=fetch(URL)
print("LIST",len(doc),final,h.get("content-type"))
for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
    txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
    if "2026년 7월 상임감사 업무추진비 집행 내역" in txt or "2026년 7월 기획운영이사 업무추진비 집행내역" in txt:
        print("\nROW\n",html.unescape(row)[:12000])
for m in re.finditer(r"<a\b[^>]*href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>",doc,re.I|re.S):
    href=html.unescape(m.group(1))
    txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    if "2026년 7월" in txt and any(k in txt for k in ("상임감사","기획운영이사","능력개발이사","능력평가이사")):
        print("LINK",txt,urllib.parse.urljoin(URL,href))
