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
        b=r.read()
        enc=r.headers.get_content_charset() or "utf-8"
        return b.decode(enc,"replace"),r.geturl(),r.headers
for key,url in TARGETS.items():
    print("\n\n====",key,"====")
    try:doc,final,h=fetch(url)
    except Exception as e:
        print("FETCH_ERROR",type(e).__name__,e);continue
    print("FETCH",len(doc),final,h.get("content-type"))
    pats={
      "KOAT":["2026년 9월 기관장 업무추진비","expenseInst","article","view","file","download"],
      "FIRA":["기관장 및 임원 업무추진비성 경비내역","첨부","file","down","download","35749"],
      "NILE":["2026년 8월 중 기관장 업무추진비","2026년 8월중 기관장 업무추진비","download","file","atch","134"],
    }[key]
    for p in pats:
        idx=doc.find(p)
        if idx>=0:
            print("\nMATCH",p,"\n",html.unescape(doc[max(0,idx-1200):idx+3500]))
    print("\nATTRS")
    for m in re.finditer(r"(?:href|onclick|action|src)\s*=\s*['\"][^'\"]{1,500}['\"]",doc,re.I):
        s=html.unescape(m.group(0))
        low=s.lower()
        if any(k in low for k in ("download","file","attach","atch","article","expense","board","view")):
            print(s[:700])
