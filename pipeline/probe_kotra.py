#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.request
URL="https://www.kotra.or.kr/kotra/module/beffatPlbc/selectBeffatPlbcUsrListItemAjax.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
req=urllib.request.Request(URL,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9","Referer":"https://www.kotra.or.kr/kp/subList/20000005799"})
with urllib.request.urlopen(req,timeout=20) as r:
    raw=r.read(); enc=r.headers.get_content_charset() or "utf-8"
doc=raw.decode(enc,"replace")
print("PAGE",len(raw))
for m in re.finditer(r"<script\b[^>]*>(.*?)</script>",doc,re.I|re.S):
    s=html.unescape(m.group(1))
    if "Bplbc" in s or "bplbc" in s or "ajax" in s.lower() or "subtd_" in s:
        print("\nSCRIPT_BLOCK\n",s[:20000])
for m in re.finditer(r'["\']([^"\']*(?:beffatPlbc|Bplbc|bplbc)[^"\']*)["\']',doc,re.I):
    print("URLISH",html.unescape(m.group(1)))
