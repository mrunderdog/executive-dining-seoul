#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.request
URL="https://www.kobc.or.kr/ebz/kor/bbs/view.do?bIdx=98052&mId=0601020400&ptIdx=341"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); enc=r.headers.get_content_charset() or "utf-8"
    print("STATUS",len(raw),r.geturl(),r.headers.get("content-type"))
doc=raw.decode(enc,"replace")
needle="2026년 8월 상임이사 업무추진비 집행내역.pdf"
i=doc.find(needle)
print("INDEX",i)
if i>=0:
    print(html.unescape(doc[max(0,i-4000):i+5000]))
for pat in (r"function\s+[^\s(]*(?:down|file)[^\s(]*\s*\([^)]*\)\s*\{.*?\}",):
    for m in re.finditer(pat,doc,re.I|re.S):
        print("\nFUNC\n",html.unescape(m.group(0))[:7000])

for src in ("/ebz/common/renewal/js/common/EgovFileUtils.js","/ebz/dwr/interface/EgovFileMngDwr.js"):
    u="https://www.kobc.or.kr"+src
    try:
        req=urllib.request.Request(u,headers={"User-Agent":UA,"Referer":URL})
        with urllib.request.urlopen(req,timeout=20) as r:
            s=r.read().decode("utf-8","replace")
        if "fn_egov_downFile" in s or "downFile" in s:
            print("\nSCRIPT",u,"\n",s[:12000])
    except Exception as e: print("ERR",u,e)
