#!/usr/bin/env python3
from __future__ import annotations
import io, json, re, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="hug"
INSTITUTION="주택도시보증공사"
LISTING="https://www.khug.or.kr/openapi/web/go/th/goth000003.jsp?id=1035&subCategory=20841"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def fetch(url:str,referer:str="")->bytes:
    req=urllib.request.Request(url,headers={
        "User-Agent":UA,"Accept":"*/*","Accept-Language":"ko-KR,ko;q=0.9,en-US;q=0.7",
        "Referer":referer or LISTING,
    })
    with urllib.request.urlopen(req,timeout=12) as r:return r.read()

def text_fetch(url:str)->str:
    raw=fetch(url)
    for enc in ("utf-8","cp949","euc-kr"):
        try:return raw.decode(enc)
        except Exception:pass
    return raw.decode("utf-8",errors="replace")

def _discover_files(year:int):
    years={year,year-1};files=[];pages=[];errors=[]
    urls=[LISTING]+[LISTING+f"&currentPage={i}" for i in range(2,5)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        fm={pool.submit(text_fetch,u):u for u in urls}
        for fut in as_completed(fm):
            u=fm[fut]
            try:doc=fut.result()
            except Exception as e:
                errors.append(f"listing {u}: {type(e).__name__}: {e}");continue
            pages.append(u)
            for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
                txt=" ".join(re.sub(r"<[^>]+>"," ",row).replace("&nbsp;"," ").split())
                ym=re.search(r"(20\d{2})년\s*(\d{1,2})월\s*기관장\s*및\s*상임이사",txt)
                if not ym:continue
                y,m=int(ym.group(1)),int(ym.group(2))
                if y not in years:continue
                dm=re.search(r'href=["\']([^"\']*?/khugcms/board/skin/download\.jsp\?[^"\']+)["\']',row,re.I)
                if not dm:continue
                dl=urllib.parse.urljoin(u,dm.group(1).replace("&amp;","&"))
                q=urllib.parse.parse_qs(urllib.parse.urlsplit(dl).query)
                files.append({"text":f"{y}년 {m}월 기관장 및 상임이사 업무추진비.pdf",
                              "url":dl,"download_url":dl,"parent":u,"year":y,"month":m,
                              "attachment_id":f"{q.get('id',[''])[0]}|{q.get('fileId',[''])[0]}"})
    uniq={x["url"]:x for x in files}
    return sorted(uniq.values(),key=lambda x:(x["year"],x["month"])),pages,errors

def _parse_pdf(att:dict):
    try:
        from pypdf import PdfReader
        blob=fetch(att["url"],att.get("parent",""))
        pdf=PdfReader(io.BytesIO(blob))
    except Exception as e:
        return [],f"pdf {att['url']}: {type(e).__name__}: {e}"
    rows=[]
    for pi,page in enumerate(pdf.pages,start=1):
        text=page.extract_text(extraction_mode="layout") or ""
        hm=re.search(r"□\s*20\d{2}년\s*\d{1,2}월\s*중\s*(.+?)\s*업무추진비\s*집행내역",text)
        role=" ".join(hm.group(1).split()) if hm else ""
        if not role:continue
        for li,line in enumerate(text.splitlines(),start=1):
            line=line.strip()
            if not re.match(r"20\d{2}-\d{2}-\d{2}\s+",line):continue
            cells=[x.strip() for x in re.split(r"\s{2,}",line) if x.strip()]
            if len(cells)<7:continue
            date=cells[0]; amount_text=cells[-1]; people_text=cells[-2]
            method=cells[-3]; target=cells[-4]; merchant=cells[-5]
            purpose=" ".join(cells[1:-5]).strip()
            try:amount=int(amount_text.replace(",",""))
            except Exception:amount=None
            try:people=int(re.search(r"\d+",people_text).group())
            except Exception:people=None
            if not merchant:continue
            rows.append({
                "source_key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
                "role":role,"department":"","used_date":date,"used_time":"",
                "merchant":merchant,"address":"","purpose":purpose,"people":people,"amount":amount,
                "source_amount_scale":1,"payment_method":method,"source_category":"","target":target,
                "source_url":att["url"],"source_sheet":f"page-{pi}","source_row":li,
                "row_id":f"hug:{att['attachment_id']}:{pi}:{li}",
            })
    return rows,None

def discover(year:int)->dict:
    attachments,pages,errors=_discover_files(year)
    out={"key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
         "default_role":"기관장·상임이사","years":[year-1,year],"pages":pages,
         "attachments":attachments,"inline_rows":[],"inline_replace":True,"errors":errors}
    if attachments:
        with ThreadPoolExecutor(max_workers=min(5,len(attachments))) as pool:
            fm={pool.submit(_parse_pdf,a):a for a in attachments}
            for fut in as_completed(fm):
                parsed,err=fut.result();out["inline_rows"].extend(parsed)
                if err:out["errors"].append(err)
    out["inline_rows"].sort(key=lambda r:(r["used_date"],r["role"],r["row_id"]))
    out["parseable_attachments"]=len(attachments)
    out["status"]="PARSEABLE_FOUND" if out["inline_rows"] else ("FETCH_FAILED" if out["errors"] else "NO_FILES_FOUND")
    return out

def main():
    payload=json.loads(REPORT.read_text(encoding="utf-8"))
    fresh=discover(int(payload.get("year") or datetime.now().year))
    payload["sources"]=[x for x in payload.get("sources",[]) if x.get("key")!=KEY]+[fresh]
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"key":KEY,"status":fresh["status"],"attachments":len(fresh["attachments"]),
      "rows":len(fresh["inline_rows"]),"merchants":len({r["merchant"] for r in fresh["inline_rows"]}),
      "roles":sorted({r["role"] for r in fresh["inline_rows"]}),"errors":fresh["errors"][:5]},ensure_ascii=False))

if __name__=="__main__":main()
