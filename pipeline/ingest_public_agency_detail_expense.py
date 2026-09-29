#!/usr/bin/env python3
from __future__ import annotations

import argparse, html, json, re
from pathlib import Path
from urllib.parse import urljoin, urlencode

import requests
from bs4 import BeautifulSoup

from ingest_public_agency_executive_expense import read_workbook, meal_like, t

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"sources"/"public_agency_registry.json"
OUT=ROOT/"data"/"raw"/"public_agency_detail_expense.json"
REPORT=ROOT/"reports"/"public-agency-detail-ingestion.json"
MD=ROOT/"reports"/"public-agency-detail-ingestion.md"
UA="Mozilla/5.0 (compatible; ExecutiveDining/1.0; +https://github.com/mrunderdog/executive-dining-seoul)"


def clean_merchant(v:str)->tuple[str,str]:
    s=t(v).replace("\n"," ")
    phone=""
    m=re.search(r"(?:☎|전화)?\s*(0\d{1,2}[- )]?\d{3,4}[- ]?\d{4}|15\d{2}-\d{4}|0507[- ]?\d{3,4}[- ]?\d{4})",s)
    if m:
        phone=re.sub(r"\s+","",m.group(1))
    s=re.sub(r"\([^)]*(?:☎|전화)[^)]*\)","",s)
    s=re.sub(r"\s+"," ",s).strip(" -·")
    return s,phone


def korail_discover(session:requests.Session,list_url:str,pages:int)->list[dict]:
    seen={}
    for page in range(1,pages+1):
        sep="&" if "?" in list_url else "?"
        u=f"{list_url}{sep}pageIndex={page}"
        r=session.get(u,timeout=35)
        r.raise_for_status()
        soup=BeautifulSoup(r.text,"html.parser")
        for tr in soup.find_all("tr"):
            text=" ".join(tr.stripped_strings)
            if "업무추진비 집행내역" not in text:
                continue
            if not ("기관장" in text or "사장직무대행" in text):
                continue
            a=tr.find("a",href=re.compile(r"selectBbsNttView\.do"))
            if not a:
                continue
            href=html.unescape(a.get("href") or "")
            m=re.search(r"nttNo=(\d+)",href)
            if not m:
                continue
            ntt=m.group(1)
            detail=urljoin(r.url,href.replace(";jsessionid="+re.search(r";jsessionid=([^?]+)",href).group(1),"") if ";jsessionid=" in href else href)
            title=text
            seen[ntt]={"ntt_no":ntt,"title":title,"detail_url":detail}
    return list(seen.values())


def korail_ingest(session:requests.Session,items:list[dict],max_items:int)->tuple[list[dict],list[dict]]:
    raw=[]
    status=[]
    for item in sorted(items,key=lambda x:int(x["ntt_no"]),reverse=True)[:max_items]:
        st={"ntt_no":item["ntt_no"],"title":item["title"],"detail_url":item["detail_url"],"state":"ERROR"}
        try:
            r=session.get(item["detail_url"],timeout=35)
            r.raise_for_status()
            soup=BeautifulSoup(r.text,"html.parser")
            links=[]
            for a in soup.find_all("a",href=re.compile(r"downloadBbsFile\.do")):
                href=a.get("href") or ""
                name=" ".join(a.parent.stripped_strings) if a.parent else " ".join(a.stripped_strings)
                links.append({"url":urljoin(r.url,href),"name":name})
            st["attachments"]=len(links)
            parsed_count=0
            meal_count=0
            for link in links:
                if "xlsx" not in link["name"].lower() and "xls" not in link["name"].lower():
                    continue
                fr=session.get(link["url"],timeout=45)
                fr.raise_for_status()
                rows=read_workbook(fr.content)
                parsed_count+=len(rows)
                for row in rows:
                    merchant,phone=clean_merchant(row.get("merchant"))
                    if not merchant:
                        continue
                    row=dict(row)
                    row["merchant"]=merchant
                    row["phone"]=phone
                    row["agency_id"]="korail"
                    row["agency_name"]="한국철도공사"
                    row["source_file"]=link["name"]
                    row["source_url"]=item["detail_url"]
                    row["source_ntt_no"]=item["ntt_no"]
                    if not meal_like(row):
                        continue
                    meal_count+=1
                    raw.append(row)
            st["parsed_rows"]=parsed_count
            st["meal_rows"]=meal_count
            st["state"]="MERCHANT_LEVEL" if parsed_count else "NO_PARSEABLE_XLS"
        except Exception as exc:
            st["error"]=f"{type(exc).__name__}: {exc}"
        status.append(st)
        print(json.dumps(st,ensure_ascii=False))
    return raw,status


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--korail-pages",type=int,default=3)
    ap.add_argument("--korail-items",type=int,default=24)
    args=ap.parse_args()

    reg=json.loads(REGISTRY.read_text(encoding="utf-8"))
    korail=next((a for a in reg.get("agencies",[]) if a.get("id")=="korail"),None)
    if not korail or not korail.get("detail_source"):
        raise SystemExit("korail detail source missing")

    session=requests.Session()
    session.headers.update({"User-Agent":UA})
    items=korail_discover(session,korail["detail_source"]["list_url"],args.korail_pages)
    rows,status=korail_ingest(session,items,args.korail_items)

    doc={
      "schema_version":1,
      "source":"기관 자체 정보공개 상세 업무추진비",
      "rows":rows,
      "sources":{"korail":{"discovered":len(items),"processed":len(status),"status":status}},
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    rep={
      "discovered":len(items),
      "processed":len(status),
      "merchant_rows":len(rows),
      "months_with_rows":sum(x.get("meal_rows",0)>0 for x in status),
      "errors":sum(x.get("state")=="ERROR" for x in status),
      "status":status,
    }
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md=[
      "# 공공기관 상세 업무추진비 수집",
      "",
      f"- 코레일 게시물 발견: {rep['discovered']}건",
      f"- 처리: {rep['processed']}건",
      f"- 식사성 사용처 행: {rep['merchant_rows']}건",
      f"- 식사성 행이 있는 게시물: {rep['months_with_rows']}건",
      f"- 오류: {rep['errors']}건",
      "",
      "| 게시물 | 상태 | 원자료행 | 식사성행 |",
      "|---|---|---:|---:|",
    ]
    for x in status:
        md.append(f"| {x['title']} | {x['state']} | {x.get('parsed_rows',0)} | {x.get('meal_rows',0)} |")
    MD.write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps(rep,ensure_ascii=False))


if __name__=="__main__":
    main()
