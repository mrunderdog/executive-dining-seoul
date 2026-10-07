#!/usr/bin/env python3
import re,html,urllib.request
URL="https://www.nps.or.kr/pbcpgdnc/bzadpblnt/getOHAG0028M0List.do?menuId=MN24001026"
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0","Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=15) as r:
    raw=r.read();doc=raw.decode(r.headers.get_content_charset() or "utf-8",errors="replace")
print("LEN",len(doc))
for m in re.finditer(r"<a\b([^>]*)>(.*?)</a>",doc,re.I|re.S):
    attrs=m.group(1); text=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    hm=re.search(r"href=[\"']([^\"']+)[\"']",attrs,re.I);href=html.unescape(hm.group(1)) if hm else ""
    om=re.search(r"onclick=[\"']([^\"']+)[\"']",attrs,re.I);onclick=html.unescape(om.group(1)) if om else ""
    s=text+" "+href+" "+onclick
    if "2026년 4월" in s or "download" in s.lower() or "첨부" in s or "pstId=" in s:
        print("LINK",repr(text),repr(href),repr(onclick))
for token in ("fileDown","download","atchFile","fileId","pstId","fileSn","fileSeq"):
    if token.lower() in doc.lower():print("TOKEN",token)

for m in re.finditer(r"fncAtchFileDownload\s*\((.*?)\)",doc,re.I|re.S):
    print("CALL", " ".join(m.group(0).split())[:500])
for m in re.finditer(r"function\s+fncAtchFileDownload\s*\([^)]*\)\s*\{.*?\}",doc,re.I|re.S):
    print("DEF", " ".join(m.group(0).split())[:1500])

for m in re.finditer(r"<script[^>]+src=[\"']([^\"']+)[\"']",doc,re.I):
    src=html.unescape(m.group(1))
    if any(k in src.lower() for k in ("common","file","board","global","util")):
        print("SCRIPT",src)
for m in re.finditer(r"<form\b([^>]*)>",doc,re.I|re.S):
    a=re.search(r"action=[\"']([^\"']+)[\"']",m.group(1),re.I)
    if a: print("FORM",html.unescape(a.group(1)))
for m in re.finditer(r"(?:atch|file)[^\"'<>]{0,120}(?:download|down)[^\"'<>]{0,160}",doc,re.I):
    print("FILESNIP"," ".join(doc[max(0,m.start()-100):m.end()+160].split())[:600])

for js in ("/js/ui_common.js","/js/common/common_utils.js","/js/common/ui_contents.js"):
    try:
        u="https://www.nps.or.kr"+js
        req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Referer":URL})
        with urllib.request.urlopen(req,timeout=12) as r:
            j=r.read().decode(r.headers.get_content_charset() or "utf-8",errors="replace")
        print("JSLEN",js,len(j))
        if "fncAtchFileDownload" in j:
            p=j.index("fncAtchFileDownload")
            print("JSDEF",js," ".join(j[max(0,p-500):p+1800].split()))
    except Exception as e:
        print("JSERR",js,type(e).__name__,e)
