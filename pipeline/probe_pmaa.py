#!/usr/bin/env python3
from __future__ import annotations
import html,io,re,urllib.parse,urllib.request,http.cookiejar
from pypdf import PdfReader

BASE="https://www.pmaa.or.kr"
LIST=BASE+"/www/1461128776985/bbs.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def open_req(url,data=None,referer=LIST):
    req=urllib.request.Request(url,data=data,headers={
        "User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9",
        "Referer":referer,
        **({"Content-Type":"application/x-www-form-urlencoded"} if data is not None else {})
    })
    return opener.open(req,timeout=20)

with open_req(LIST) as r:
    r.read()
print("COOKIES1",[(c.name,c.value[:30]) for c in jar])

detail_data=urllib.parse.urlencode({"type":"view","bbsIdx":"42469"}).encode()
with open_req(LIST,detail_data,LIST) as r:
    doc=r.read().decode(r.headers.get_content_charset() or "utf-8","replace")
print("COOKIES2",[(c.name,c.value[:30]) for c in jar])

m=re.search(r"fn_www_download2\('([^']+)','([^']+)','([^']+)','([^']+)'\)",doc)
print("META",m.groups() if m else None)
if not m: raise SystemExit("download meta not found")
endpoint,path,physical,original=m.groups()
data=urllib.parse.urlencode({"path":path,"physicalName":physical,"original":original}).encode()
with open_req(urllib.parse.urljoin(BASE,endpoint),data,LIST) as r:
    blob=r.read()
    print("DOWNLOAD",len(blob),r.geturl(),r.headers.get("content-type"),r.headers.get("content-disposition"),blob[:8])
if not blob.startswith(b"%PDF"):
    print(blob[:2000].decode("utf-8","replace"))
    raise SystemExit("not pdf")
reader=PdfReader(io.BytesIO(blob))
print("PAGES",len(reader.pages))
for i,p in enumerate(reader.pages[:6],1):
    try: txt=p.extract_text(extraction_mode="layout") or ""
    except Exception: txt=p.extract_text() or ""
    print("\nPAGE",i,"\n",txt[:16000])
