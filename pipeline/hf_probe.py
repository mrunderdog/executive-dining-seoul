#!/usr/bin/env python3
import re, urllib.request, html
from html.parser import HTMLParser

UA="Mozilla/5.0"
URLS=[
 ("기관장","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_01.do"),
 ("감사","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_02.do"),
 ("임원","https://www.hf.go.kr/ko/sub05/sub05_03_04_05_03.do"),
]

class P(HTMLParser):
    def __init__(self): super().__init__(); self.a=[]; self.cur=None
    def handle_starttag(self,tag,attrs):
        if tag.lower()=="a":
            d=dict(attrs); self.cur={"href":d.get("href",""),"onclick":d.get("onclick",""),"text":[]}
    def handle_data(self,d):
        if self.cur is not None:self.cur["text"].append(d)
    def handle_endtag(self,tag):
        if tag.lower()=="a" and self.cur is not None:
            self.cur["text"]=" ".join(" ".join(self.cur["text"]).split());self.a.append(self.cur);self.cur=None

for role,url in URLS:
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=15) as r:
        doc=r.read().decode(r.headers.get_content_charset() or "utf-8","replace")
    print("PAGE",role,"LEN",len(doc))
    p=P();p.feed(doc)
    for a in p.a:
        blob=(a["text"]+" "+a["href"]+" "+a["onclick"])
        if re.search(r"202[56]|xlsx|attach|download|articleNo",blob,re.I):
            print("A",role,repr(a["text"]),repr(a["href"]),repr(a["onclick"]))
