#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request

URL="https://www.kotra.or.kr/kp/subList/20000005799"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
def fetch(url,referer=URL):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9","Referer":referer})
    with urllib.request.urlopen(req,timeout=20) as r:
        return r.read(),r.geturl(),r.headers
raw,final,h=fetch(URL)
doc=raw.decode(h.get_content_charset() or "utf-8","replace")
print("PAGE",len(raw),final,h.get("content-type"))
for needle in ("fnSubBplbcListToggle","selectBeffatPlbcUsrListItemAjax","subtd_"):
    i=doc.find(needle)
    print("\nNEEDLE",needle,"IDX",i)
    if i>=0: print(html.unescape(doc[max(0,i-5000):i+10000]))
for m in re.finditer(r"<script\b[^>]*src=['\"]([^'\"]+)['\"]",doc,re.I):
    src=urllib.parse.urljoin(URL,html.unescape(m.group(1)))
    try:
        b,u,hh=fetch(src)
        s=b.decode(hh.get_content_charset() or "utf-8","replace")
        if "fnSubBplbcListToggle" in s or "selectBeffatPlbcUsr" in s:
            i=max(s.find("fnSubBplbcListToggle"),s.find("selectBeffatPlbcUsr"))
            print("\nSCRIPT",u,"\n",s[max(0,i-5000):i+10000])
    except Exception:
        pass
