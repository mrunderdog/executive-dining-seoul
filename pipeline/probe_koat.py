#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request,http.cookiejar

URL="https://m.koat.or.kr/board/expenseInst/list.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def fetch(url,data=None,referer=URL):
    req=urllib.request.Request(url,data=data,headers={
        "User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9","Referer":referer,
        "Origin":"https://m.koat.or.kr" if data is not None else "https://m.koat.or.kr"
    })
    with opener.open(req,timeout=20) as r:
        return r.read(),r.geturl(),r.headers

raw,final,h=fetch(URL)
doc=raw.decode(h.get_content_charset() or "utf-8","replace")
print("LIST",len(raw),final,h.get("content-type"),"COOKIES",[(c.name,c.value[:20]) for c in jar])
sigm=re.search(r'name=["\']ptSignature["\'][^>]*value=["\']([^"\']+)["\']',doc,re.I)
sig=html.unescape(sigm.group(1)) if sigm else ""
print("SIG",bool(sig),len(sig))
data=urllib.parse.urlencode({"ptSignature":sig,"mode":"","name":"","key":"14015"}).encode()
blob,u,hh=fetch("https://m.koat.or.kr/download.do",data,URL)
print("DOWNLOAD",len(blob),u,hh.get("content-type"),hh.get("content-disposition"),blob[:16])
print("COOKIES2",[(c.name,c.value[:20]) for c in jar])
if (hh.get("content-type") or "").lower().startswith("text/"):
    print("TEXT_HEAD",blob[:1200].decode(hh.get_content_charset() or "utf-8","replace"))
