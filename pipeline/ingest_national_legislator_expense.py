#!/usr/bin/env python3
from __future__ import annotations

import hashlib, io, json, re, urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW_DIR=ROOT/"data"/"raw"; REPORTS=ROOT/"reports"
UA="ExecutiveDiningSeoul/2.1 (+https://github.com/mrunderdog/executive-dining-seoul)"
FILES=[
 ("21대","https://raw.githubusercontent.com/OhmyNews/KA-money/master/2024_KAPF-21.xlsx"),
 ("22대","https://raw.githubusercontent.com/OhmyNews/KA-money/master/2024_KAPF-22.xlsx"),
]
ALIASES={
 "member":["의원명"],"party":["당","정당"],"district":["지역명","지역구"],
 "date":["연월일","날짜","지출일"],"purpose":["내역","지출내역","내용"],
 "amount":["지출액","금액"],"merchant":["사용처","지출받은자","지출처"],"category":["분류 항목","분류항목","분류"]}

def clean(v):return " ".join(str(v or "").replace("\n"," ").split()).strip()
def nh(v):return re.sub(r"[\s()\[\]·ㆍ._/-]+","",clean(v)).lower()
def fetch(url):
 req=urllib.request.Request(url,headers={"User-Agent":UA});
 with urllib.request.urlopen(req,timeout=90) as r:return r.read()
def pdate(v):
 if isinstance(v,datetime):return v.date().isoformat()
 if isinstance(v,date):return v.isoformat()
 s=clean(v);m=re.search(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})",s)
 if m:
  try:return date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
  except:pass
 return s
def amount(v):
 if isinstance(v,(int,float)) and not isinstance(v,bool):return int(round(v))
 s=re.sub(r"[^0-9.-]","",clean(v));
 try:return int(round(float(s))) if s else None
 except:return None
def find_header(rows):
 best=(-1,-1,{})
 for i,row in enumerate(rows[:40]):
  mp={}
  for j,c in enumerate(row):
   x=nh(c)
   for field,als in ALIASES.items():
    if field not in mp and x and any(nh(a)==x or nh(a) in x for a in als):mp[field]=j
  score=sum(k in mp for k in ("member","date","purpose","amount","merchant"))
  if score>best[0]:best=(score,i,mp)
 return best if best[0]>=4 else None
def cell(row,mp,k):
 i=mp.get(k);return row[i] if i is not None and i<len(row) else None

def main():
 import openpyxl
 all_rows=[];files=[];errors=[]
 for assembly,url in FILES:
  try:
   blob=fetch(url);wb=openpyxl.load_workbook(io.BytesIO(blob),read_only=True,data_only=True)
   parsed=0
   for ws in wb.worksheets:
    rows=[list(r) for r in ws.iter_rows(values_only=True)];h=find_header(rows)
    if not h:continue
    _,hi,mp=h
    for ri,row in enumerate(rows[hi+1:],start=hi+2):
     member=clean(cell(row,mp,"member"));merchant=clean(cell(row,mp,"merchant"));amt=amount(cell(row,mp,"amount"));d=pdate(cell(row,mp,"date"))
     if not member or (not merchant and amt is None):continue
     r={"assembly":assembly,"member":member,"party":clean(cell(row,mp,"party")),"district":clean(cell(row,mp,"district")),"used_date":d,"purpose":clean(cell(row,mp,"purpose")),"amount":amt,"merchant":merchant,"category":clean(cell(row,mp,"category")),"cohort":"national_legislator","source_url":url,"source_sheet":ws.title,"source_row":ri}
     r["row_id"]=hashlib.sha256("|".join(str(r.get(k,"")) for k in ("assembly","member","used_date","merchant","amount","source_sheet","source_row")).encode()).hexdigest()[:20]
     all_rows.append(r);parsed+=1
   files.append({"assembly":assembly,"url":url,"bytes":len(blob),"parsed_rows":parsed})
  except Exception as e:errors.append({"assembly":assembly,"url":url,"error":f"{type(e).__name__}: {e}"})
 unique={r["row_id"]:r for r in all_rows};rows=sorted(unique.values(),key=lambda r:(r.get("used_date") or "",r.get("member") or "",r["row_id"]))
 RAW_DIR.mkdir(exist_ok=True);out=RAW_DIR/"national_legislator_2024_expense.json";out.write_text(json.dumps({"schema_version":1,"source":"OhmyNews/KA-money","upstream":"Central Election Commission political-fund accounting reports obtained via information disclosure","year":2024,"row_count":len(rows),"rows":rows,"files":files,"errors":errors},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
 md=["# National legislator political-fund ingestion — 2024","","> Source lineage: Central Election Commission accounting reports → information-disclosure PDFs → OhmyNews/Kyunghyang/Newstapa OCR/normalization → this project.","",f"- Rows: **{len(rows)}**",f"- Files: **{len(files)}**",f"- Errors: **{len(errors)}**"]
 (REPORTS/"national-legislator-ingestion.md").write_text("\n".join(md)+"\n",encoding="utf-8")
 print(json.dumps({"rows":len(rows),"files":len(files),"errors":len(errors)},ensure_ascii=False))

if __name__=="__main__":main()
