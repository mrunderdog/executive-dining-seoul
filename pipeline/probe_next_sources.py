#!/usr/bin/env python3
from __future__ import annotations
import html,io,re,urllib.parse,urllib.request
from pypdf import PdfReader

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def req(url,data=None,referer=""):
    h={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"}
    if referer:h["Referer"]=referer
    r=urllib.request.Request(url,data=data,headers=h)
    with urllib.request.urlopen(r,timeout=30) as x:
        return x.read(),x.geturl(),x.headers

# KOAT
list_url="https://m.koat.or.kr/board/expenseInst/list.do"
raw,_,_=req(list_url)
doc=raw.decode("utf-8","replace")
sig=re.search(r'<form name="downForm"[^>]*>\s*<input type="hidden" name="ptSignature" value="([^"]+)"',doc,re.S)
print("KOAT_SIG",bool(sig))
data=urllib.parse.urlencode({"ptSignature":html.unescape(sig.group(1)),"mode":"1","key":"14015"}).encode()
blob,u,h=req("https://m.koat.or.kr/download.do",data,list_url)
print("KOAT_FILE",len(blob),u,h.get("content-type"),h.get("content-disposition"),blob[:8])
if blob[:4]==b"%PDF":
    text="\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(blob)).pages)
    print("KOAT_TEXT\n",text[:12000])

# FIRA
fu="https://www.fira.or.kr/_custom/cms/_common/board/fira.jsp?attach_no=36135"
blob,u,h=req(fu,referer="https://www.fira.or.kr/fira/fira_050602_3.jsp?article_no=35749&board_no=186&mode=view")
print("FIRA_FILE",len(blob),u,h.get("content-type"),h.get("content-disposition"),blob[:8])
if blob[:4]==b"%PDF":
    text="\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(blob)).pages)
    print("FIRA_TEXT\n",text[:16000])

# NILE: print exact method from page around function implementation
nu="https://www.nile.or.kr/usr/wap/list.do?app=12716&lang=ko&listAll=Y"
raw,_,_=req(nu)
nd=raw.decode("utf-8","replace")
for needle in ["fileListDownLoad: function","fileListDownLoad = function","fileListDownLoad(item)","downloadFileUrl","fileDownloadUrl","getFileUrl"]:
    i=nd.find(needle)
    print("NILE_NEEDLE",needle,i)
    if i>=0: print(nd[max(0,i-2500):i+9000])
