#!/usr/bin/env python3
import re,urllib.request,html
URL="https://www.alio.go.kr/upload/disclosure/2025/04/10/2025041002972278/doc.html"
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0"})
with urllib.request.urlopen(req,timeout=15) as r:
    raw=r.read();doc=raw.decode(r.headers.get_content_charset() or "utf-8","replace")
print("LEN",len(doc))
patterns=[
 r'apbaId[^A-Za-z0-9]+([A-Za-z0-9]+)',
 r'disclosureNo[^0-9]+([0-9]{10,})',
 r'fileNo[^0-9]+([0-9]+)',
 r'href=["\']([^"\']*(?:download|file)[^"\']*)["\']',
 r'["\']([^"\']+\.xlsx?)["\']'
]
for pat in patterns:
    vals=[]
    for m in re.finditer(pat,doc,re.I):
        v=m.group(1)
        if v not in vals: vals.append(v)
    print("PAT",pat,vals[:40])
for token in ("제주국제자유도시개발센터","2024년 기관장 업무추진비","집행상세내역","report_attach_down"):
    i=doc.find(token)
    print("CTX",token," ".join(doc[max(0,i-600):i+1600].split()) if i>=0 else "MISS")

print("SCRIPTS", re.findall(r'<script[^>]+src=["\\']([^"\\']+)["\\']',doc,re.I)[:30])
