#!/usr/bin/env python3
from __future__ import annotations
import io, json, time, urllib.parse, urllib.request
from pypdf import PdfReader

BASE="https://www.kibo.or.kr"
LISTING=BASE+"/main/board/boardType46.do?article.offset=0&mode=list"
ENDPOINT=BASE+"/COMN0201/attchLocalFileDownload.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

FILES=[
    ("기관장","JWATTCH-54-65231","file1","9f65f3d8-2769-54de-2873-0ce42481ac00"),
    ("임원","JWATTCH-54-65232","file1","96ca2c2e-9412-4e4f-fbd6-dbb09fa341fe"),
]

for role,file_id,file_div,file_key in FILES:
    data=urllib.parse.urlencode({
        "attchFileDiv":file_div,
        "attchFileId":file_id,
        "attchFileKey":file_key,
        "downComplTocken":"probe",
    }).encode()
    req=urllib.request.Request(ENDPOINT,data=data,headers={
        "User-Agent":UA,
        "Accept":"*/*",
        "Accept-Language":"ko-KR,ko;q=0.9",
        "Referer":LISTING,
        "Content-Type":"application/x-www-form-urlencoded",
    })
    last=None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req,timeout=20) as r:
                blob=r.read()
                print("DOWNLOAD",role,len(blob),r.geturl(),r.headers.get("content-type"),r.headers.get("content-disposition"),blob[:8])
            break
        except Exception as e:
            last=e
            print("DOWNLOAD_RETRY",role,attempt+1,type(e).__name__,e)
            time.sleep(2*(attempt+1))
    else:
        raise last
    pdf=PdfReader(io.BytesIO(blob))
    print("PAGES",role,len(pdf.pages))
    for pi,page in enumerate(pdf.pages[:3],start=1):
        txt=" ".join((page.extract_text() or "").split())
        print("PAGE",role,pi,txt[:12000])
