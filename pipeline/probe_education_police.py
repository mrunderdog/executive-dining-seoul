#!/usr/bin/env python3
"""Read-only diagnostics for official education/police expense posting and attachments."""
from __future__ import annotations
import html, json, re, urllib.request
from html.parser import HTMLParser

URLS = {
    "goe_head": "https://www.goe.go.kr/goe/na/ntt/selectNttList.do?bbsId=1955&mi=10239",
    "goe_exec": "https://www.goe.go.kr/goe/na/ntt/selectNttList.do?bbsId=1956&mi=10240",
    "goe_detail": "https://www.goe.go.kr/goe/na/ntt/selectNttInfo.do?mi=10240&nttSn=109232",
    "ice_head": "https://www.ice.go.kr/ice/na/ntt/selectNttList.do?bbsId=1726&mi=11654",
    "ice_vice": "https://www.ice.go.kr/ice/na/ntt/selectNttInfo.do?bbsAllView=Y&bbsId=2128&nttSn=3380591",
    "ice_detail": "https://www.ice.go.kr/ice/na/ntt/selectNttInfo.do?bbsAllView=Y&bbsId=1726&nttSn=3380590",
    "police_list": "https://www.police.go.kr/user/bbs/BD_selectBbsList.do?q_bbsCode=1025&q_code=005003&q_detailCode=005003006",
    "police_detail": "https://www.police.go.kr/user/bbs/BD_selectBbs.do?q_bbsCode=1025&q_bbscttSn=20260325092542533",
}
class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        raw=" ".join(f"{k}={v}" for k,v in attrs)
        if (tag in {"a","button","input","form"} and
            (tag == "a" or re.search(r"ntt|file|down|bbs|attach|download",raw,re.I))):
            self.tags.append({"tag":tag,"attrs":dict(list(d.items())[:10])})
def run():
    result={}
    for key,url in URLS.items():
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept-Language":"ko-KR,ko;q=0.9"})
            with urllib.request.urlopen(req,timeout=22) as r:
                body=r.read(1300000)
                enc=r.headers.get_content_charset() or "utf-8"
                raw=body.decode(enc,errors="replace")
                print(key,"HTTP",r.status,"BYTES",len(body),"content_type",r.headers.get("Content-Type"))
            p=Tags();p.feed(raw)
            found=[]
            for x in p.tags:
                info=json.dumps(x,ensure_ascii=False)
                if (key.endswith("detail") or key=="ice_vice" or "selectNttInfo" in info
                        or "q_bbscttSn" in info or "nttSn" in info):
                    found.append(info[:320])
            file_context=[]
            for m in list(re.finditer(r"(?:첨부파일|\.pdf|\.xlsx|download|nttFile|fileId|attach)",raw,re.I))[:18]:
                file_context.append(re.sub(r"\s+"," ",html.unescape(raw[max(m.start()-110,0):m.end()+130]))[:250])
            result[key]={"status":"ok","links":found[:20],"file_context":file_context[:12],
                         "nttSn_matches":list(dict.fromkeys(re.findall(r"nttSn[^0-9]{0,8}(\d{5,})",raw)))[:16],
                         "police_id_matches":list(dict.fromkeys(re.findall(r"q_bbscttSn[^0-9]{0,8}(\d{10,})",raw)))[:12]}
        except Exception as e:
            result[key]={"status":"failed","error":f"{type(e).__name__}: {e}"}
    print("SOURCE_PROBE_RESULT_START")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print("SOURCE_PROBE_RESULT_END")
if __name__=="__main__": run()
