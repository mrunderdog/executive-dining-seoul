#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request
LIST="https://www.kofpi.or.kr/public/publicInfo_03_001.do?sub=26"
VIEW="https://www.kofpi.or.kr/public/publicInfo_03_001view.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
data=urllib.parse.urlencode({"cPage":"1","bb_seq":"12673","subtype":"26"}).encode()
req=urllib.request.Request(VIEW,data=data,headers={
    "User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9","Referer":LIST,
    "Content-Type":"application/x-www-form-urlencoded"
})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read();enc=r.headers.get_content_charset() or "utf-8"
    print("STATUS",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
needle="2026년 임원 업무추진비 집행내역(8월)"
i=doc.find(needle)
print("TITLE_IDX",i)
if i>=0:print(html.unescape(doc[max(0,i-2500):i+7000]))
for m in re.finditer(r"<a\b[^>]*(?:href|onclick)=['\"]([^'\"]*)['\"][^>]*>(.*?)</a>",doc,re.I|re.S):
    full=html.unescape(m.group(0)); txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    if any(k in (txt+" "+full).lower() for k in ("첨부","file","download",".pdf",".xlsx",".xls",".hwp")):
        print("\nA",full[:5000])
for pat in (r"function\s+[^\s(]*(?:down|file)[^\s(]*\s*\([^)]*\)\s*\{.*?\}",):
    for m in re.finditer(pat,doc,re.I|re.S):
        print("\nFUNC\n",html.unescape(m.group(0))[:7000])

for pat in (r"function\s+fnNotiDownload\s*\([^)]*\)\s*\{.*?\}",):
    for m in re.finditer(pat,doc,re.I|re.S):
        print("\nDOWNLOAD_FUNC\n",html.unescape(m.group(0))[:7000])

for m in re.finditer(r"<script\b[^>]*src=['\"]([^'\"]+)['\"]",doc,re.I):
    src=urllib.parse.urljoin(VIEW,html.unescape(m.group(1)))
    try:
        req=urllib.request.Request(src,headers={"User-Agent":UA,"Referer":VIEW})
        with urllib.request.urlopen(req,timeout=20) as r:
            js=r.read().decode(r.headers.get_content_charset() or "utf-8","replace")
        if "fnNotiDownload" in js:
            i=js.find("fnNotiDownload")
            print("\nSCRIPT_FUNC",src,"\n",js[max(0,i-3000):i+7000])
    except Exception:
        pass
