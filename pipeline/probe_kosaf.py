#!/usr/bin/env python3
from __future__ import annotations
import html, io, re, urllib.parse, urllib.request, zipfile
import xml.etree.ElementTree as ET

URL="https://www.kosaf.go.kr/ko/openinfo.do?ctgrId1=0000000015&pg=operation10"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def get(url, data=None, referer=URL):
    headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9","Referer":referer}
    req=urllib.request.Request(url,data=data,headers=headers)
    with urllib.request.urlopen(req,timeout=20) as r:
        raw=r.read()
        return raw, r.geturl(), r.headers

raw,final,h=get(URL)
doc=raw.decode("utf-8","replace")
print("LIST",len(raw),final,h.get("content-type"))

for pat in (r"function\s+fileDown\s*\([^)]*\)\s*\{.*?\}", r"fileDown\s*=\s*function\s*\([^)]*\)\s*\{.*?\}"):
    for m in re.finditer(pat,doc,re.I|re.S):
        print("\nFILEDOWN DEF\n",html.unescape(m.group(0))[:5000])

for m in re.finditer(r"<script\b[^>]*src=['\"]([^'\"]+)['\"]",doc,re.I):
    src=urllib.parse.urljoin(URL,html.unescape(m.group(1)))
    if any(k in src.lower() for k in ("common","util","file","board","open")):
        try:
            b,u,hh=get(src)
            s=b.decode("utf-8","replace")
            if "fileDown" in s:
                i=s.find("fileDown")
                print("\nSCRIPT",u,"\n",s[max(0,i-2000):i+5000])
        except Exception as e:
            print("SCRIPT_ERR",src,type(e).__name__,e)

items=[]
for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
    txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
    ym=re.search(r"(20\d{2})년도\s*(\d{1,2})월\s*(기관장|상임감사|상임이사)\s*업무추진비",txt)
    fm=re.search(r"fileDown\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",row,re.I)
    if ym and fm and int(ym.group(1))>=2025:
        items.append((ym.groups(),fm.groups(),txt))
print("\nITEMS",items[:12])

# Print all forms around possible file download handling.
for m in re.finditer(r"<form\b.*?</form>",doc,re.I|re.S):
    s=html.unescape(m.group(0))
    if any(k in s for k in ("fileDown","fileId","UPLOAD","file")):
        print("\nFORM\n",s[:7000])
