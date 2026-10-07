#!/usr/bin/env python3
from __future__ import annotations

import html, io, json, re, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="nile"
INSTITUTION="국가평생교육진흥원"
LISTING="https://www.nile.or.kr/usr/wap/list.do?app=12716&lang=ko&listAll=Y"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def fetch(url:str,referer:str="")->bytes:
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={
                "User-Agent":UA,
                "Accept":"*/*",
                "Accept-Language":"ko-KR,ko;q=0.9,en-US;q=0.7",
                "Referer":referer or LISTING,
                "Connection":"close",
            })
            with urllib.request.urlopen(req,timeout=25) as r:
                return r.read()
        except Exception as e:
            last=e
            if attempt<2: time.sleep(1.0+attempt)
    raise last

def text_fetch(url:str)->str:
    raw=fetch(url)
    for enc in ("utf-8","cp949","euc-kr"):
        try:return raw.decode(enc)
        except Exception:pass
    return raw.decode("utf-8","replace")

def _discover_files(year:int):
    years={year,year-1};files=[];pages=[];errors=[]
    # The NILE board is rate-sensitive. Four pages cover the current and
    # previous calendar years while avoiding the disconnects seen on broad
    # parallel scans of all historical pages.
    urls=[LISTING]+[
        f"https://www.nile.or.kr/usr/wap/list.do?app=12716&lang=ko&listAll=Y&pageIndex={p}"
        for p in range(2,5)
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        fm={pool.submit(text_fetch,u):u for u in urls}
        for fut in as_completed(fm):
            u=fm[fut]
            try:doc=fut.result()
            except Exception as e:
                errors.append(f"listing {u}: {type(e).__name__}: {e}");continue
            pages.append(u)
            # NILE renders each board item as a JS object in var list = [...]
            pat=re.compile(
                r"'nttSeq'\s*:\s*'(?P<ntt>\d+)'.*?"
                r"'nttSj'\s*:\s*'(?P<title>[^']+)'.*?"
                r"'atchFileSeq'\s*:\s*'(?P<atch>\d+)'.*?"
                r"'atchFileSeqFiles'\s*:\s*\[(?P<files>.*?)\]",
                re.S
            )
            for m in pat.finditer(doc):
                title=html.unescape(m.group("title"))
                ym=re.search(r"(20\d{2})년\s*(\d{1,2})월.*기관장\s*업무추진비",title)
                if not ym:continue
                y,mo=int(ym.group(1)),int(ym.group(2))
                if y not in years:continue
                fm2=re.search(
                    r"'fileSn'\s*:\s*'(?P<sn>\d+)'.*?"
                    r"'orignlFileNm'\s*:\s*'(?P<name>[^']+)'",
                    m.group("files"),re.S
                )
                if not fm2:continue
                ntt,atch=m.group("ntt"),m.group("atch")
                sn=fm2.group("sn");name=html.unescape(fm2.group("name"))
                dl="https://www.nile.or.kr/usr/wap/downloadFile.do?"+urllib.parse.urlencode({
                    "app":"12716","seq":ntt,"atchFileSeq":atch,
                    "fileColumn":"atchFileSeq","fileSn":sn,"lang":"ko",
                })
                files.append({
                    "text":title,"url":dl,"download_url":dl,"parent":u,
                    "year":y,"month":mo,"attachment_id":f"{ntt}|{atch}|{sn}",
                    "filename":name,
                })
    uniq={x["attachment_id"]:x for x in files}
    return sorted(uniq.values(),key=lambda x:(x["year"],x["month"])),pages,errors

def _norm_date(s:str)->str:
    m=re.search(r"(20\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?",s)
    if not m:return ""
    try:return datetime(*map(int,m.groups())).date().isoformat()
    except ValueError:return ""

def _clean_merchant(s:str)->str:
    s=re.sub(r"\(☎?[^)]*\)"," ",s)
    s=re.sub(r"☎?0\d{1,2}-\d{3,4}-\d{4}"," ",s)
    return " ".join(s.split()).strip()

def _parse_pdf(att:dict):
    try:
        from pypdf import PdfReader
        blob=fetch(att["url"],att.get("parent",""))
        pdf=PdfReader(io.BytesIO(blob))
    except Exception as e:
        return [],f"pdf {att['url']}: {type(e).__name__}: {e}"
    rows=[]
    for pi,page in enumerate(pdf.pages,start=1):
        try:text=page.extract_text(extraction_mode="layout") or ""
        except Exception:text=page.extract_text() or ""
        for li,line in enumerate(text.splitlines(),start=1):
            if not re.match(r"\s*20\d{2}\.\s*\d{1,2}\.\s*\d{1,2}\.",line):continue
            cells=[x.strip() for x in re.split(r"\s{2,}",line.strip()) if x.strip()]
            if len(cells)<7:continue
            date=_norm_date(cells[0])
            if not date:continue
            amount_text=cells[-1];people_text=cells[-2]
            method=cells[-3];target=cells[-4];merchant=_clean_merchant(cells[-5])
            purpose=" ".join(cells[1:-5]).strip()
            if not merchant or merchant in {"-","해당없음"}:continue
            try:amount=int(re.sub(r"[^0-9]","",amount_text))
            except Exception:amount=None
            try:
                pm=re.search(r"\d+",people_text);people=int(pm.group()) if pm else None
            except Exception:people=None
            rows.append({
                "source_key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
                "role":"기관장","department":"","used_date":date,"used_time":"",
                "merchant":merchant,"address":"","purpose":purpose,
                "people":people,"amount":amount,"source_amount_scale":1,
                "payment_method":method,"source_category":"기관장","target":target,
                "source_url":att["url"],"source_sheet":f"page-{pi}","source_row":li,
                "row_id":f"nile:{att['attachment_id']}:{pi}:{li}",
            })
    return rows,None

def discover(year:int)->dict:
    attachments,pages,errors=_discover_files(year)
    rows=[]
    if attachments:
        with ThreadPoolExecutor(max_workers=min(2,len(attachments))) as pool:
            fm={pool.submit(_parse_pdf,a):a for a in attachments}
            for fut in as_completed(fm):
                parsed,err=fut.result();rows.extend(parsed)
                if err:errors.append(err)
    rows.sort(key=lambda r:(r["used_date"],r["row_id"]))
    return {
        "key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
        "default_role":"기관장","years":[year-1,year],"pages":pages,
        "attachments":attachments,"inline_rows":rows,"inline_replace":True,
        "errors":errors,"parseable_attachments":len(attachments),
        "status":"PARSEABLE_FOUND" if rows else ("FETCH_FAILED" if errors else "NO_FILES_FOUND"),
    }

def main():
    payload=json.loads(REPORT.read_text(encoding="utf-8"))
    fresh=discover(int(payload.get("year") or datetime.now().year))
    payload["sources"]=[x for x in payload.get("sources",[]) if x.get("key")!=KEY]+[fresh]
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
        "key":KEY,"status":fresh["status"],"attachments":len(fresh["attachments"]),
        "rows":len(fresh["inline_rows"]),
        "merchants":len({r["merchant"] for r in fresh["inline_rows"]}),
        "errors":fresh["errors"][:8],
    },ensure_ascii=False))

if __name__=="__main__":main()
