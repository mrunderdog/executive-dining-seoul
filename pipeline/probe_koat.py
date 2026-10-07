#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://m.koat.or.kr/board/expenseInst/list.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req,timeout=20) as r:
        raw=r.read()
        return raw.decode(r.headers.get_content_charset() or "utf-8","replace"),r.geturl(),r.headers
doc,final,h=fetch(URL)
print("LIST",len(doc),final)
for pat in [
    r"function\s+fn_borad_file_down\s*\([^)]*\)\s*\{.*?\}",
    r"fn_borad_file_down\s*=\s*function\s*\([^)]*\)\s*\{.*?\}",
]:
    for m in re.finditer(pat,doc,re.I|re.S):
        print("FUNC",html.unescape(m.group(0))[:5000])

for m in re.finditer(r"<script\b[^>]*src=['\"]([^'\"]+)['\"]",doc,re.I):
    src=urllib.parse.urljoin(URL,html.unescape(m.group(1)))
    try:s,_,_=fetch(src)
    except Exception:continue
    if "fn_borad_file_down" in s:
        i=s.find("fn_borad_file_down")
        print("SCRIPT",src,s[max(0,i-2500):i+5000])

print("MENU LINKS")
for m in re.finditer(r"<a\b[^>]*href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>",doc,re.I|re.S):
    href=html.unescape(m.group(1)); txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    if "업무추진비" in txt or "임원" in txt:
        print(txt,urllib.parse.urljoin(URL,href))
