#!/usr/bin/env python3
"""Read-only public board markup audit for broken council adapters.

Print a few source rows and clickable attributes. Never download attachments.
"""
import argparse
import html
import re
import urllib.request
from capital_backfill import SOURCES, decode_html, UA

def inspect(source):
    s=next(x for x in SOURCES if x.key==source)
    url=s.listing_template.format(page=1)
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            raw=r.read(2_500_000)
            body=decode_html(raw,r.headers.get_content_charset())
            print(f"=== {source} === status={r.status} url={r.geturl()} bytes={len(raw)}")
    except Exception as e:
        print(f"=== {source} === ERROR {type(e).__name__}: {e}")
        return
    print("form elements:",[html.unescape(x)[:350] for x in re.findall(r'<form\b[^>]*>',body,re.I)[:4]])
    print("onClick counts:",len(re.findall("onclick",body,re.I)),"tr count:",len(re.findall(r'<tr\b',body,re.I)))
    rows=re.findall(r'<tr\b[^>]*>.*?</tr>',body,re.I|re.S)
    count=0
    for row in rows:
        if '업무추진비' not in row and not re.search(r'2026.{0,35}분기',row): continue
        plain=" ".join(re.sub(r'<[^>]+>',' ',html.unescape(row)).split())
        print(f"ROW {count}: {plain[:170]}")
        print("HTML:",re.sub(r'\s+',' ',row)[:1550])
        count+=1
        if count>=3: break
    for matched in re.finditer(r'<a\b[^>]*>',body,re.I|re.S):
        token=matched.group(0)
        if any(k in token.lower() for k in ('onclick','bbs','javascript','download','view')) and count < 8:
            print("A:",html.unescape(token)[:380])
            count+=1
    for key in ['boardView','fn_view','fnView','goView','viewPage','fileDown','fnDownload','download']:
        matches=list(re.finditer(re.escape(key),body,re.I))
        if matches:
            m=matches[0]
            print("JS:",key,re.sub(r'\s+',' ',body[max(0,m.start()-100):m.start()+480])[:550])
    if source in ("hwaseong","ansan","dongducheon"):
        for fn in ("goViewPage", "fnGoDetail"):
            m=re.search(r"function\s+"+fn+r"\s*\([^)]*\)\s*\{",body,re.I)
            if m:print("FUNCTION",fn,re.sub(r"\s+"," ",body[m.start():m.start()+1900]))
        for token in ("bbsViewPageGoFrm", "bbsSn", "fnGoDetail", "bbs_idx", "bbs_id", "list_frm_submit"):
            m=re.search(re.escape(token),body,re.I)
            if m:print("CONTEXT",token,re.sub(r"\s+"," ",body[max(0,m.start()-270):m.start()+650]))
    if source=="hwaseong":
        try:
            script="https://council.hscity.go.kr/js/svc/filedownload.js?ver=2020707"
            with urllib.request.urlopen(urllib.request.Request(script,headers={"User-Agent":UA}),timeout=15) as r:
                script_body=r.read(200000).decode("utf-8",errors="replace")
            print("DOWNLOAD SCRIPT",script,"bytes",len(script_body),"BODY:",repr(script_body[:2500]))
            for fn in ("fileDownLoad", "fileDownload"):
                for m in list(re.finditer(r"function\\s+"+fn+r"\\s*\\([^)]*\\)\\s*\\{",script_body,re.I))[:2]:
                    print("DOWNLOAD FUNCTION",re.sub(r"\\s+"," ",script_body[m.start():m.start()+1300]))
        except Exception as e:
            print("DOWNLOAD SCRIPT ERROR",type(e).__name__,str(e))

        from capital_backfill import council_js_posts, fetch_text
        pages=council_js_posts(s,url,body,(2026,7),(2026,10))
        for p in pages[:2]:
            try:
                d=fetch_text(p["post_url"])
                print("DETAIL",p["post_url"],"bytes",len(d))
                for tag in re.findall(r'<a\b[^>]*>.*?</a>',d,re.I|re.S):
                    if re.search(r'fileDownLoad|xlsx?|\.xls|첨부파일|download',tag,re.I):
                        print("FILE ANCHOR:",re.sub(r"\s+"," ",html.unescape(tag))[:1200])
                for tag in re.findall(r'<input\b[^>]*>',d,re.I|re.S):
                    if re.search(r'file|bbsSn|atch',tag,re.I):
                        print("DETAIL INPUT:",re.sub(r"\s+"," ",tag)[:650])
                for fn in ("fileDownLoad","filedownload","download"):
                    for m in list(re.finditer(re.escape(fn),d,re.I))[:5]:
                        print("DOWNLOAD CONTEXT",fn,re.sub(r"\s+"," ",d[max(0,m.start()-220):m.start()+380])[:600])
            except Exception as e:
                print("DETAIL ERROR",p["post_url"],type(e).__name__,str(e))
    print("=== end",source,"===")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--source",action="append",required=True);a=p.parse_args()
    for source in a.source:inspect(source)
