#!/usr/bin/env python3
from __future__ import annotations
import html, re, urllib.request

URL="https://www.kosaf.go.kr/ko/operation.do?pg=operation07_28"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read()
    ct=r.headers.get("content-type","")
print("STATUS",len(raw),ct)
doc=raw.decode("utf-8","replace")

patterns=[
    r"2026년도\s*8월\s*기관장\s*업무추진비\s*집행내역",
    r"2026년도\s*8월\s*상임감사\s*업무추진비\s*집행내역",
    r"2026년도\s*8월\s*상임이사\s*업무추진비\s*집행내역",
]
for pat in patterns:
    m=re.search(pat,doc,re.I)
    print("\nPATTERN",pat,"FOUND",bool(m))
    if m:
        lo=max(0,m.start()-1200); hi=min(len(doc),m.end()+1600)
        print(html.unescape(doc[lo:hi]))

print("\nFORMS/SCRIPTS")
for m in re.finditer(r"(?:onclick|href|action)\s*=\s*['\"][^'\"]{0,300}['\"]",doc,re.I):
    s=html.unescape(m.group(0))
    if any(k in s.lower() for k in ("operation","file","down","view","detail")):
        print(s[:500])

print("\nHIDDEN INPUTS")
for m in re.finditer(r"<input\b[^>]*type=['\"]hidden['\"][^>]*>",doc,re.I):
    s=html.unescape(m.group(0))
    if any(k in s.lower() for k in ("seq","idx","no","id","file","pg")):
        print(s[:500])
