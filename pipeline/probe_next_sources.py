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
        b=r.read(); enc=r.headers.get_content_charset() or "utf-8"
        return b.decode(enc,"replace"),r.geturl(),r.headers

for key,url in TARGETS.items():
    print("\n====",key,"====")
    try:doc,final,h=fetch(url)
    except Exception as e:
        print("FETCH_ERROR",type(e).__name__,e);continue
    print("FETCH",len(doc),final)
    pats = {
      "KOAT":[r"function\s+fn_borad_file_down\s*\([^)]*\)\s*\{.*?\}",r"fn_borad_file_down\([^\n]+",r"<form[^>]+name=['\"]downForm['\"].*?</form>"],
      "FIRA":[r"첨부파일.*?</tr>",r"(?:href|onclick)=['\"][^'\"]*(?:download|file|attach)[^'\"]*['\"]",r"fileView\([^\n]+",r"35749.{0,3000}"],
      "NILE":[r"fileListDownLoad\s*\([^)]*\)\s*\{.*?\}",r"fileDownLoad\s*\([^)]*\)\s*\{.*?\}",r"/js/onioncms/vu2/fms/atchFile.js"],
    }[key]
    for pat in pats:
        print("\nPAT",pat)
        ms=list(re.finditer(pat,doc,re.I|re.S))
        for m in ms[:8]:
            print(html.unescape(m.group(0))[:9000])

    # inspect relevant JS
    for sm in re.finditer(r"<script\b[^>]*src=['\"]([^'\"]+)['\"]",doc,re.I):
        src=urllib.parse.urljoin(final,html.unescape(sm.group(1)))
        if key=="KOAT" and any(x in src.lower() for x in ("common","board","main")) or \
           key=="NILE" and "atchfile" in src.lower():
            try:
                js,ju,_=fetch(src)
            except Exception as e:
                print("JSERR",src,e);continue
            if any(x in js for x in ("fn_borad_file_down","fileListDownLoad","atchFile","download")):
                print("\nJS",ju)
                for needle in ("fn_borad_file_down","fileListDownLoad","download","atchFile"):
                    i=js.find(needle)
                    if i>=0: print(js[max(0,i-2500):i+7000])
