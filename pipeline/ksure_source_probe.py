#!/usr/bin/env python3
import re,html,urllib.request
URL="https://www.ksure.or.kr/rh-kr/bbs/i-480/list.do"
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0","Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=15) as r:
    raw=r.read();doc=raw.decode(r.headers.get_content_charset() or "utf-8",errors="replace")
print("LEN",len(doc))
for m in re.finditer(r"<a\b([^>]*)>(.*?)</a>",doc,re.I|re.S):
    attrs=m.group(1);text=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    hm=re.search(r"href=[\"']([^\"']+)[\"']",attrs,re.I);href=html.unescape(hm.group(1)) if hm else ""
    om=re.search(r"onclick=[\"']([^\"']+)[\"']",attrs,re.I);onclick=html.unescape(om.group(1)) if om else ""
    s=text+" "+href+" "+onclick
    if any(k in s for k in ("2026년 기관장","2026년 상임감사","2026년 상임이사","Excel")) or "download" in s.lower():
        print("LINK",repr(text),repr(href),repr(onclick))
for token in ("fileNo","fileSn","atchFileId","download","excel","bbsNo","nttId"):
    if token.lower() in doc.lower():print("TOKEN",token)
