#!/usr/bin/env python3
from __future__ import annotations
import json,time,urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

START="https://www.kosha.or.kr/esg/management-disclosure/self-disclosure/executive-expenses/research-director"
ROLE_TEXTS={"기관장","상임감사 및 이사","연구원장","교육원장","인증원장","스마트안전보건 기술원장(폐지)"}
o=Options()
o.add_argument("--headless=new"); o.add_argument("--no-sandbox"); o.add_argument("--disable-gpu")
o.add_argument("--window-size=1440,1200")
o.set_capability("goog:loggingPrefs",{"performance":"ALL"})
d=webdriver.Chrome(options=o)

def drain():
    try:return d.get_log("performance")
    except:return []

def decode_post(s):
    try:
        q=urllib.parse.parse_qs(s)
        v=(q.get("_JSON") or [""])[0]
        for _ in range(2):
            nv=urllib.parse.unquote(v)
            if nv==v:break
            v=nv
        return json.loads(v)
    except Exception:return None

try:
    d.execute_cdp_cmd("Network.enable",{})
    d.get(START); time.sleep(6)
    links=[]
    for a in d.find_elements(By.TAG_NAME,"a"):
        txt=(a.text or "").strip()
        href=a.get_attribute("href") or ""
        if txt in ROLE_TEXTS:
            links.append((txt,href))
    print("ROLE_LINKS",json.dumps(links,ensure_ascii=False))
    for role,href in links:
        if not href: continue
        drain()
        d.get(href); time.sleep(5)
        print("\n=== ROLE",role,href,"===")
        print("BODY_HEAD",d.find_element(By.TAG_NAME,"body").text[:4500].replace("\n"," | "))
        logs=drain()
        requests={}
        responses={}
        for e in logs:
            try:
                m=json.loads(e["message"])["message"]; p=m["params"]
                if m["method"]=="Network.requestWillBeSent":
                    req=p["request"]
                    if "/stdtboard/process.do" in req["url"]:
                        requests[p["requestId"]]=req
                elif m["method"]=="Network.responseReceived":
                    res=p["response"]
                    if "/stdtboard/process.do" in res["url"]:
                        responses[p["requestId"]]=res
            except: pass
        for rid,req in requests.items():
            dec=decode_post(req.get("postData",""))
            if not dec: continue
            t=dec.get("common",{}).get("data",{}).get("tboard",{})
            print("REQ",json.dumps({
                "serviceId":t.get("serviceId"),"bbsId":t.get("bbsId"),
                "serviceData":dec.get("service",{}).get("data",{})
            },ensure_ascii=False))
            if t.get("serviceId")=="basicAccess" and rid in responses:
                try:
                    body=d.execute_cdp_cmd("Network.getResponseBody",{"requestId":rid}).get("body","")
                    print("RESP",body[:16000])
                except Exception as ex:
                    print("RESP_ERR",type(ex).__name__,ex)
finally:
    d.quit()
