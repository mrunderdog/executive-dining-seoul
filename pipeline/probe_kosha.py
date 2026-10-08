#!/usr/bin/env python3
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
URL="https://www.kosha.or.kr/esg/management-disclosure/self-disclosure/executive-expenses/auditorndirector"
o=Options();o.add_argument("--headless=new");o.add_argument("--no-sandbox");o.add_argument("--disable-gpu")
d=webdriver.Chrome(options=o)
try:
 d.get(URL);time.sleep(6)
 for i,s in enumerate(d.find_elements(By.TAG_NAME,"select")):
  print("SELECT",i,s.get_attribute("outerHTML")[:12000])
finally:d.quit()
