#!/usr/bin/env python3
import re, html, urllib.request
from html.parser import HTMLParser

URLS=[
("기관장","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_01.do?articleNo=600602&mode=view"),
("감사","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_02.do?articleNo=600603&mode=view"),
("임원","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_03.do?articleNo=600604&mode=view"),
]
class P(HTMLParser):
    def __init__(self): super().__init__(); self.a=[]; self.cur=None
    def handle_starttag(self,t,attrs):
        if t.lower()=="a": self.cur=dict(attrs); self.cur["text"]=[]
    def handle_data(self,d):
        if self.cur is not None:self.cur["text"].append(d)
    def handle_endtag(self,t):
        if t.lower()=="a" and self.cur is not None:
            self.cur["text"]=" ".join(" ".join(self.cur["text"]).split());self.a.append(self.cur);self.cur=None
for role,url in URLS:
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept-Language":"ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req,timeout=15) as r: doc=r.read().decode(r.headers.get_content_charset() or "utf-8",errors="replace")
    print("PAGE",role,len(doc))
    p=P();p.feed(doc)
    for a in p.a:
        text=a.get("text",""); href=html.unescape(a.get("href",""))
        if "xlsx" in text.lower() or "내려받기" in text or "download" in href.lower() or "file" in href.lower():
            print("LINK",role,repr(text),repr(href),repr(a.get("onclick","")))
