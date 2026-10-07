#!/usr/bin/env python3
from __future__ import annotations
import html,re,urllib.parse,urllib.request
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"
TARGETS={
 "KOAT":"https://m.koat.or.kr/board/expenseInst/list.do",
 "FIRA":"https://www.fira.or.kr/fira/fira_050602_3.jsp?article_no=35749&board_no=186&board_wrapper=%2Ffira%2Ffira_050602_3.jsp&mode=view&pager.offset=0",
 "NILE":"https://www.nile.or.kr/usr/wap/list.do?app=12716&lang=ko&listAll=Y",
}
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req,timeout=20) as r:
        b=r.read();enc=r.headers.get_content_charset() or "utf-8"
        return b.decode(enc,"replace"),r.geturl(),r.headers
for key,url in TARGETS.items():
    print("\n====",key,"====")
    try:doc,final,h=fetch(url)
    except Exception as e: print("ERR",e);continue
    needles={
      "KOAT":["function fn_borad_file_down","downForm.action","download.do","fileDown.do"],
      "FIRA":["function download","attach_no=36135","javascript:download('36135')"],
      "NILE":["fileListDownLoad","downloadFileUrl","downloadUrl","/fms/","atchFileSeq"],
    }[key]
    for n in needles:
      start=0
      while True:
        i=doc.find(n,start)
        if i<0:break
        print("\nNEEDLE",n,"\n",html.unescape(doc[max(0,i-2200):i+7000]))
        start=i+len(n)
        if start>i+20000:break
