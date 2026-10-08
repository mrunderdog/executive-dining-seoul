#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://m.koat.or.kr/board/expenseInst/list.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def fetch(url,referer=URL):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9","Referer":referer})
    with urllib.request.urlopen(req,timeout=20) as r:
        return r.read(),r.geturl(),r.headers

raw,final,h=fetch(URL)
doc=raw.decode(h.get_content_charset() or "utf-8","replace")
print("LIST",len(raw),final,h.get("content-type"))

for pat in (r"function\s+fn_borad_file_down\s*\([^)]*\)\s*\{.*?\}",r"fn_borad_file_down\s*=\s*function\s*\([^)]*\)\s*\{.*?\}"):
    for m in re.finditer(pat,doc,re.I|re.S):
        print("\nDEF\n",html.unescape(m.group(0))[:8000])

for m in re.finditer(r"<script\b[^>]*src=['\"]([^'\"]+)['\"]",doc,re.I):
    src=urllib.parse.urljoin(URL,html.unescape(m.group(1)))
    try:
        b,u,hh=fetch(src)
        s=b.decode(hh.get_content_charset() or "utf-8","replace")
        if "fn_borad_file_down" in s:
            i=s.find("fn_borad_file_down")
            print("\nSCRIPT",u,"\n",s[max(0,i-3000):i+7000])
    except Exception as e:
        pass

for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
    txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
    if "2026년 9월 기관장 업무추진비 집행내역" in txt:
        print("\nROW\n",html.unescape(row)[:8000])
