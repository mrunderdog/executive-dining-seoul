#!/usr/bin/env python3
import re,html,urllib.parse,urllib.request
URL="https://www.khug.or.kr/openapi/web/go/th/goth000003.jsp?id=1035&subCategory=20841"
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0","Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=15) as r:
    raw=r.read();doc=raw.decode(r.headers.get_content_charset() or "utf-8",errors="replace")
print("LEN",len(doc))
for pat in ("기관장","상임이사","업무추진비","사용장소","2026","2025"):
    print("HAS",pat,pat in doc)
for m in re.finditer(r"<a\b([^>]*)>(.*?)</a>",doc,re.I|re.S):
    attrs=m.group(1); text=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    hm=re.search(r"href=[\"']([^\"']+)[\"']",attrs,re.I); href=html.unescape(hm.group(1)) if hm else ""
    om=re.search(r"onclick=[\"']([^\"']+)[\"']",attrs,re.I); onclick=html.unescape(om.group(1)) if om else ""
    s=text+" "+href+" "+onclick
    if any(k in s.lower() for k in ("업무추진","download","file","attach","2026","2025")):
        print("LINK",repr(text),repr(href),repr(onclick))
for token in ("fileId","download.jsp","articleId","board","subCategory","ajax","json","2026년","2025년"):
    if token.lower() in doc.lower():print("TOKEN",token)
for m in re.finditer(r"download[^\"'<>]{0,160}",doc,re.I):
    print("SNIP", " ".join(doc[max(0,m.start()-120):m.end()+220].split())[:500])
