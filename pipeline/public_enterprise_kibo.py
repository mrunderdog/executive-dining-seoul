#!/usr/bin/env python3
from __future__ import annotations

import html, io, json, re, subprocess, tempfile, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="kibo"
INSTITUTION="기술보증기금"
LISTING="https://www.kibo.or.kr/main/board/boardType46.do?mode=list"
DOWNLOAD="https://www.kibo.or.kr/COMN0201/attchLocalFileDownload.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def fetch_text(url:str)->str:
    last=None
    for i in range(4):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"})
            with urllib.request.urlopen(req,timeout=18) as r:
                return r.read().decode(r.headers.get_content_charset() or "utf-8","replace")
        except Exception as e:
            last=e
            time.sleep(i+1)
    raise last

def download(att:dict)->bytes:
    data=urllib.parse.urlencode({
        "attchFileDiv":att["file_div"],
        "attchFileId":att["file_id"],
        "attchFileKey":att["file_key"],
        "downComplTocken":"kibo-ingest",
    }).encode()
    last=None
    for i in range(3):
        try:
            req=urllib.request.Request(DOWNLOAD,data=data,headers={
                "User-Agent":UA,"Accept":"*/*","Accept-Language":"ko-KR,ko;q=0.9",
                "Referer":att["parent"],"Content-Type":"application/x-www-form-urlencoded",
            })
            with urllib.request.urlopen(req,timeout=18) as r:
                blob=r.read()
                if blob.startswith(b"%PDF"): return blob
                raise RuntimeError(f"unexpected payload {blob[:16]!r}")
        except Exception as e:
            last=e
            time.sleep(2*(i+1))
    # DNS to kibo.or.kr is intermittently flaky on GitHub runners.
    cmd=[
        "curl","-fSL","--retry","8","--retry-all-errors","--retry-delay","2",
        "--connect-timeout","6","--max-time","25","-A",UA,"-e",att["parent"],
        "-d",f"attchFileDiv={att['file_div']}",
        "-d",f"attchFileId={att['file_id']}",
        "-d",f"attchFileKey={att['file_key']}",
        DOWNLOAD,
    ]
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=120)
        if p.stdout.startswith(b"%PDF"): return p.stdout
        raise RuntimeError(f"curl unexpected payload {p.stdout[:16]!r}")
    except Exception:
        raise last

def _discover(year:int):
    years={year,year-1};items=[];pages=[];errors=[]
    for offset in range(0,80,10):
        url=LISTING+f"&article.offset={offset}&articleLimit=10"
        try:doc=fetch_text(url)
        except Exception as e:
            errors.append(f"listing {url}: {type(e).__name__}: {e}");continue
        pages.append(url)
        page_years=[]
        for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
            txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
            ym=re.search(r"(20\d{2})년\s*(\d{1,2})월\s*(기관장|임원)\s*업무추진비\s*집행내역",txt)
            if not ym:continue
            y,mo,role=int(ym.group(1)),int(ym.group(2)),ym.group(3)
            page_years.append(y)
            if y not in years:continue
            fm=re.search(
                r'<a\b[^>]*data-file-id=["\']([^"\']+)["\'][^>]*'
                r'data-file-vl=["\']([^"\']+)["\'][^>]*'
                r'data-file-key=["\']([^"\']+)["\'][^>]*'
                r'class=["\'][^"\']*file-down-btn[^"\']*["\'][^>]*>',
                row,re.I|re.S
            )
            if not fm:
                # Attribute order has been stable, but keep an order-independent fallback.
                am={}
                for k in ("file-id","file-vl","file-key"):
                    m=re.search(rf'data-{k}=["\']([^"\']+)["\']',row,re.I)
                    if m:am[k]=m.group(1)
                if len(am)!=3:continue
                file_id,file_div,file_key=am["file-id"],am["file-vl"],am["file-key"]
            else:
                file_id,file_div,file_key=fm.groups()
            items.append({
                "year":y,"month":mo,"role":role,"text":txt,"parent":url,
                "file_id":file_id,"file_div":file_div,"file_key":file_key,
                "attachment_id":f"{file_id}|{file_div}|{file_key}",
            })
        if page_years and min(page_years)<min(years):
            break
    uniq={x["attachment_id"]:x for x in items}
    return sorted(uniq.values(),key=lambda x:(x["year"],x["month"],x["role"])),pages,errors

def _to_int(s):
    m=re.search(r"(\d{1,3}(?:,\d{3})+|\d+)",str(s or "").replace(" ",""))
    return int(m.group(1).replace(",","")) if m else None

def _parse_line(line:str,att:dict):
    line=line.strip()
    if not re.match(r"20\d{2}-\d{1,2}-\d{1,2}",line):return None
    cells=[x.strip() for x in re.split(r"\s{2,}",line) if x.strip()]
    if len(cells)<5:return None
    phone_idx=None
    for i,x in enumerate(cells):
        if re.search(r"(?:0\d{1,2}-\d{3,4}-\d{4}|15\d{2}-\d{4}|16\d{2}-\d{4})",x):
            phone_idx=i;break
    if phone_idx is None or phone_idx<2:return None

    date=cells[0]
    try:date=datetime.strptime(date[:10],"%Y-%m-%d").date().isoformat()
    except Exception:return None

    merchant=cells[phone_idx-1].strip()
    if not merchant or merchant in {"사용처(장소)","사용처"}:return None

    role=att["role"]
    if att["role"]=="임원" and phone_idx>=3:
        role=cells[phone_idx-2].strip() or "임원"
        purpose=" ".join(cells[1:phone_idx-2]).strip()
    else:
        purpose=" ".join(cells[1:phone_idx-1]).strip()

    tail=cells[phone_idx+1:]
    method=""
    for x in tail:
        if x in {"카드","법인카드","계산서","현금","계좌이체"}:
            method=x;break
    amount=_to_int(tail[-1]) if tail else None
    people=None
    if len(tail)>=2:
        for x in reversed(tail[:-1]):
            if re.fullmatch(r"\d{1,3}",x.replace(",","")):
                people=int(x.replace(",",""));break
    target=""
    for x in tail:
        if x!=method and not re.fullmatch(r"[\d,]+",x):
            target=x;break

    return {
        "source_key":KEY,"institution":INSTITUTION,
        "cohort":"public_enterprise_leadership",
        "role":role,"department":"","used_date":date,"used_time":"",
        "merchant":merchant,"address":"","purpose":purpose,
        "target":target,"people":people,"amount":amount,
        "source_amount_scale":1,"payment_method":method,
        "source_category":att["role"],
    }

def _parse_pdf(att:dict):
    try:blob=download(att)
    except Exception as e:return [],f"download {att['attachment_id']}: {type(e).__name__}: {e}"
    rows=[]
    try:
        pdf=PdfReader(io.BytesIO(blob))
        for pi,page in enumerate(pdf.pages,start=1):
            try:text=page.extract_text(extraction_mode="layout") or ""
            except Exception:text=page.extract_text() or ""
            for li,line in enumerate(text.splitlines(),start=1):
                r=_parse_line(line,att)
                if not r:continue
                r.update({
                    "source_url":DOWNLOAD,
                    "source_sheet":f"page-{pi}",
                    "source_row":li,
                    "row_id":f"kibo:{att['attachment_id']}:{pi}:{li}",
                })
                rows.append(r)
    except Exception as e:
        return [],f"parse {att['attachment_id']}: {type(e).__name__}: {e}"
    return rows,None

def discover(year:int)->dict:
    attachments,pages,errors=_discover(year);rows=[]
    if attachments:
        # KIBO DNS is unstable; keep download concurrency conservative.
        with ThreadPoolExecutor(max_workers=min(3,len(attachments))) as pool:
            fm={pool.submit(_parse_pdf,a):a for a in attachments}
            for fut in as_completed(fm):
                parsed,err=fut.result();rows.extend(parsed)
                if err:errors.append(err)
    rows.sort(key=lambda r:(r["used_date"],r["role"],r["row_id"]))
    public_atts=[{
        "text":a["text"],"url":DOWNLOAD,"download_url":DOWNLOAD,
        "year":a["year"],"month":a["month"],"parent":a["parent"],
        "attachment_id":a["attachment_id"],"role":a["role"],
    } for a in attachments]
    return {
        "key":KEY,"institution":INSTITUTION,
        "cohort":"public_enterprise_leadership",
        "default_role":"기관장·임원","years":[year-1,year],
        "pages":pages,"attachments":public_atts,
        "inline_rows":rows,"inline_replace":True,
        "errors":errors,"parseable_attachments":len(attachments),
        "status":"PARSEABLE_FOUND" if rows else ("FETCH_FAILED" if errors else "NO_FILES_FOUND"),
    }

def main():
    payload=json.loads(REPORT.read_text(encoding="utf-8"))
    fresh=discover(int(payload.get("year") or datetime.now().year))
    payload["sources"]=[x for x in payload.get("sources",[]) if x.get("key")!=KEY]+[fresh]
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
        "key":KEY,"status":fresh["status"],
        "attachments":len(fresh["attachments"]),
        "rows":len(fresh["inline_rows"]),
        "merchants":len({r["merchant"] for r in fresh["inline_rows"]}),
        "roles":sorted({r["role"] for r in fresh["inline_rows"]}),
        "date_min":min((r["used_date"] for r in fresh["inline_rows"]),default=""),
        "date_max":max((r["used_date"] for r in fresh["inline_rows"]),default=""),
        "errors":fresh["errors"][:8],
    },ensure_ascii=False))

if __name__=="__main__":
    main()
