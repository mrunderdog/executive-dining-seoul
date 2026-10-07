#!/usr/bin/env python3
import re,urllib.request,urllib.parse,html
URLS=[
 ("기관장","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_01.do?articleNo=600602&mode=view"),
 ("감사","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_02.do?articleNo=600603&mode=view"),
 ("임원","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_03.do?articleNo=600604&mode=view"),
]
UA="Mozilla/5.0"
for role,url in URLS:
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=15) as r:
        raw=r.read();doc=raw.decode(r.headers.get_content_charset() or "utf-8","replace")
    print("DETAIL",role,"LEN",len(doc))
    for m in re.finditer(r'<a\b([^>]*)>(.*?)</a>',doc,re.I|re.S):
        attrs=m.group(1);txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
        hm=re.search(r'href=["\']([^"\']+)["\']',attrs,re.I)
        om=re.search(r'onclick=["\']([^"\']+)["\']',attrs,re.I)
        href=html.unescape(hm.group(1)) if hm else ""
        onclick=html.unescape(om.group(1)) if om else ""
        blob=txt+" "+href+" "+onclick
        if re.search(r'xlsx|xls|download|attach|file',blob,re.I):
            print("A",role,repr(txt),repr(urllib.parse.urljoin(url,href)),repr(onclick))
