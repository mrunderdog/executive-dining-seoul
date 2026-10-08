#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://m.koat.or.kr/board/expenseInst/list.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
def req(url,data=None,referer=URL):
    r=urllib.request.Request(url,data=data,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9","Referer":referer})
    with urllib.request.urlopen(r,timeout=20) as x:return x.read(),x.geturl(),x.headers
raw,final,h=req(URL)
doc=raw.decode(h.get_content_charset() or "utf-8","replace")
print("LIST",len(raw),final,h.get("content-type"))
sigm=re.search(r'name=["\']ptSignature["\']\s+value=["\']([^"\']+)',doc,re.I)
sig=html.unescape(sigm.group(1)) if sigm else ""
print("SIG",bool(sig),len(sig))
for payload in (
    {"key":"14015"},
    {"key":"14015","ptSignature":sig},
    {"key":"14015","ptSignature":sig,"mode":"","name":""},
):
    data=urllib.parse.urlencode(payload).encode()
    try:
        b,u,hh=req("https://m.koat.or.kr/download.do",data)
        print("POST",list(payload),len(b),u,hh.get("content-type"),hh.get("content-disposition"),b[:16])
    except Exception as e:
        print("ERR",list(payload),type(e).__name__,e)
