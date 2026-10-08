#!/usr/bin/env python3
from __future__ import annotations
import json,time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

URL="https://www.kosha.or.kr/esg/management-disclosure/self-disclosure/executive-expenses/institution-leader"
o=Options(); o.add_argument("--headless=new"); o.add_argument("--no-sandbox"); o.add_argument("--disable-gpu")
o.add_argument("--window-size=1440,1200")
o.set_capability("goog:loggingPrefs",{"performance":"ALL"})
d=webdriver.Chrome(options=o)
try:
    d.execute_cdp_cmd("Network.enable",{})
    d.get(URL); time.sleep(6)
    els=[]
    for e in d.find_elements(By.XPATH,"//*[contains(normalize-space(text()), '다운로드')]"):
        try:
            txt=(e.text or "").strip()
            if txt=="다운로드" or "다운로드" in txt:
                els.append(e)
        except: pass
    print("DOWNLOAD_ELEMENTS",len(els))
    for i,e in enumerate(els[:8]):
        try: print("EL",i,e.tag_name,e.get_attribute("outerHTML")[:5000])
        except: pass
    d.get_log("performance")
    if els:
        try:
            d.execute_script("arguments[0].click();",els[0])
            time.sleep(4)
        except Exception as ex: print("CLICK_ERR",type(ex).__name__,ex)
    for e in d.get_log("performance"):
        try:
            m=json.loads(e["message"])["message"]; p=m["params"]
            if m["method"]=="Network.requestWillBeSent":
                req=p["request"]; u=req["url"]
                if any(k in u for k in ("fileDownload","stdtboard","download")):
                    print("REQ",req["method"],u)
                    if req.get("postData"): print("POSTDATA",req["postData"][:16000])
        except: pass
finally:
    d.quit()
