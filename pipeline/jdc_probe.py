#!/usr/bin/env python3
import re,urllib.request,html
URLS=[
 "https://www.alio.go.kr/mobile/item/itemReportTerm.do?apbaId=&disclosureNo=2025041002972278&reportFormRootNo=20701",
 "https://www.alio.go.kr/item/itemReportTerm.do?apbaId=&disclosureNo=2025041002972278&reportFormRootNo=20701",
]
for url in URLS:
  try:
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=15) as r:
      raw=r.read();doc=raw.decode(r.headers.get_content_charset() or "utf-8","replace")
    print("URL",url,"LEN",len(doc))
    for pat in [
      r'disclosureNo\s*:\s*"([^"]+)"',
      r'\$submissionNo\s*=\s*"?([0-9]+)',
      r'<option\s+value="([^"]+)">\s*([^<]+\.xlsx?)\s*</option>',
      r'apbaId[^A-Za-z0-9]+([A-Za-z0-9]+)'
    ]:
      print("PAT",pat,re.findall(pat,doc,re.I)[:30])
    i=doc.find("제주국제자유도시개발센터")
    print("CTX"," ".join(doc[max(0,i-500):i+1800].split()) if i>=0 else "MISS")
  except Exception as e:
    print("ERR",url,type(e).__name__,e)
