#!/usr/bin/env python3
from __future__ import annotations
import json,time,urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

URL="https://www.kosha.or.kr/esg/management-disclosure/self-disclosure/executive-expenses/institution-leader"
o=Options(); o.add_argument("--headless=new"); o.add_argument("--no-sandbox"); o.add_argument("--disable-gpu")
o.add_argument("--window-size=1440,1200"); o.set_capability("goog:loggingPrefs",{"performance":"ALL"})
d=webdriver.Chrome(options=o)

def decode_post(s):
    try:
        q=urllib.parse.parse_qs(s); v=(q.get("_JSON") or [""])[0]
        for _ in range(2):
            nv=urllib.parse.unquote(v)
            if nv==v:break
            v=nv
        return json.loads(v)
    except:return {}

try:
    d.execute_cdp_cmd("Network.enable",{})
    d.get(URL); time.sleep(6)
    spans=[e for e in d.find_elements(By.XPATH,"//*[normalize-space(text())='다운로드']"]
    print("DOWNLOAD_ELEMENTS",len(spans))
    d.get_log("performance")
    if spans:
        d.execute_script("arguments[0].click();",spans[0]); time.sleep(8)
    logs=d.get_log("performance")
    reqs={}; resps={}
    for e in logs:
        try:
            m=json.loads(e["message"])["message"]; p=m["params"]
            if m["method"]=="Network.requestWillBeSent":
                req=p["request"]; u=req["url"]
                if "process.do" in u or "fileDownload.do" in u:
                    reqs[p["requestId"]]=req
            elif m["method"]=="Network.responseReceived":
                res=p["response"]; u=res["url"]
                if "process.do" in u or "fileDownload.do" in u:
                    resps[p["requestId"]]=res
        except:pass
    for rid,req in reqs.items():
        dec=decode_post(req.get("postData",""))
        svc=dec.get("common",{}).get("data",{}).get("tboard",{}).get("serviceId")
        print("\nREQ",rid,req["method"],req["url"],"SERVICE",svc)
        if req.get("postData"):print("POSTDATA",req["postData"][:16000])
        if rid in resps:
            try:
                body=d.execute_cdp_cmd("Network.getResponseBody",{"requestId":rid}).get("body","")
                print("STATUS",resps[rid].get("status"),resps[rid].get("mimeType"))
                print("RESPBODY",body[:24000])
            except Exception as ex: print("RESP_ERR",type(ex).__name__,ex)
finally:d.quit()
