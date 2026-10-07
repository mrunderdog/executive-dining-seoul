#!/usr/bin/env python3
import re,html,urllib.request
URL="https://www.khug.or.kr/hug/web/cs/go/csgo000010.jsp"
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0","Accept-Language":"ko-KR,ko;q=0.9"})
with urllib.request.urlopen(req,timeout=15) as r:
    raw=r.read(); doc=raw.decode(r.headers.get_content_charset() or "utf-8",errors="replace")
print("LEN",len(doc))
for pat in ("기관장 및 상임이사","업무추진비성","사용장소","비서팀"):
    print("HAS",pat,pat in doc)
for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",doc,re.I|re.S):
    href=html.unescape(m.group(1)); text=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",m.group(2))).split())
    s=text+" "+href
    if "업무추진비" in s or "상임이사" in s or "기관장" in s or "download" in s.lower() or "file" in s.lower():
        print("LINK",repr(text),repr(href))
for token in ("cw00000123","preInfo","infoOpen","download","fileDown","articleId","bbs"):
    if token.lower() in doc.lower():print("TOKEN",token)
