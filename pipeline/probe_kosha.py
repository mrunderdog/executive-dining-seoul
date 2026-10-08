#!/usr/bin/env python3
from __future__ import annotations
import json,time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

URL="https://www.kosha.or.kr/esg/management-disclosure/self-disclosure/executive-expenses/research-director"
o=Options()
o.add_argument("--headless=new"); o.add_argument("--no-sandbox"); o.add_argument("--disable-gpu")
o.add_argument("--window-size=1440,1200")
o.set_capability("goog:loggingPrefs",{"performance":"ALL","browser":"ALL"})
d=webdriver.Chrome(options=o)
try:
    d.get(URL)
    time.sleep(8)
    print("TITLE",d.title)
    print("URL",d.current_url)
    print("BODY",d.find_element("tag name","body").text[:12000])
    seen=set()
    for e in d.get_log("performance"):
        try:
            m=json.loads(e["message"])["message"]
            if m["method"]!="Network.requestWillBeSent": continue
            p=m["params"]; req=p["request"]; u=req["url"]
            if any(k in u for k in ("/stdtboard/","/api/")):
                key=(req["method"],u,req.get("postData",""))
                if key in seen: continue
                seen.add(key)
                print("\nREQUEST",req["method"],u)
                if req.get("postData"): print("POSTDATA",req["postData"][:12000])
                hdr=req.get("headers",{})
                print("CTYPE",hdr.get("Content-Type") or hdr.get("content-type"))
        except Exception as ex:
            pass
    print("\nBROWSERLOG")
    for e in d.get_log("browser")[-30:]: print(e)
finally:
    d.quit()
