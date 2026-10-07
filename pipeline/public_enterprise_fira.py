#!/usr/bin/env python3
from __future__ import annotations

import html, io, json, re, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="fira"
INSTITUTION="한국수산자원공단"
LISTING="https://www.fira.or.kr/fira/fira_050602_3.jsp?board_no=186&board_wrapper=%2Ffira%2Ffira_050602_3.jsp&mode=list&pager.offset=0"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def fetch(url:str,referer:str="")->bytes:
    req=urllib.request.Request(url,headers={
        "User-Agent":UA,"Accept":"*/*","Accept-Language":"ko-KR,ko;q=0.9",
        "Referer":referer or LISTING,
    })
    with urllib.request.urlopen(req,timeout=20) as r:return r.read()

def text_fetch(url:str)->str:
    raw=fetch(url)
    for enc in ("utf-8","cp949","euc-kr"):
        try:return raw.decode(enc)
        except Exception:pass
    return raw.decode("utf-8","replace")

def _discover_files(year:int):
    years={year,year-1};files=[];pages=[];errors=[]
    base="https://www.fira.or.kr/fira/fira_050602_3.jsp"
    urls=[
        base+"?board_no=186&board_wrapper=%2Ffira%2Ffira_050602_3.jsp&mode=list&pager.offset="+str(off)
        for off in range(0,70,10)
    ]
    with ThreadPoolExecutor(max_workers=6) as pool:
        fm={pool.submit(text_fetch,u):u for u in urls}
        for fut in as_completed(fm):
            u=fm[fut]
            try:doc=fut.result()
            except Exception as e:
                errors.append(f"listing {u}: {type(e).__name__}: {e}");continue
            pages.append(u)
            for m in re.finditer(r'href=["\']([^"\']*mode=view[^"\']*article_no=(\d+)[^"\']*)["\'][^>]*>(.*?)</a>',doc,re.I|re.S):
                href,article,body=m.groups()
                title=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",body)).split())
                ym=re.search(r"기관장\s*및\s*임원\s*업무추진비.*?\((20\d{2})년\s*(\d{1,2})월\)",title)
                if not ym:continue
                y,mo=int(ym.group(1)),int(ym.group(2))
                if y not in years:continue
                detail=urllib.parse.urljoin(u,html.unescape(href).replace("&amp;","&"))
                try:ddoc=text_fetch(detail)
                except Exception as e:
                    errors.append(f"detail {detail}: {type(e).__name__}: {e}");continue
                am=re.search(r"javascript:download\(['\"](\d+)['\"]\)",ddoc,re.I)
                if not am:continue
                attach=am.group(1)
                dl=f"https://www.fira.or.kr/_custom/cms/_common/board/fira.jsp?attach_no={attach}"
                files.append({
                    "text":title,"url":dl,"download_url":dl,"parent":detail,
                    "year":y,"month":mo,"attachment_id":f"{article}|{attach}",
                })
    uniq={x["attachment_id"]:x for x in files}
    return sorted(uniq.values(),key=lambda x:(x["year"],x["month"])),pages,errors

def _norm_date(s:str)->str:
    m=re.search(r"(20\d{2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})",s)
    if not m:return ""
    try:return datetime(*map(int,m.groups())).date().isoformat()
    except ValueError:return ""

def _merchant_from_prefix(prefix:str)->str:
    s=" ".join(prefix.split())
    # Most FIRA merchant cells include a phone number. The merchant is the
    # final phrase immediately before that phone number.
    pm=list(re.finditer(r"\(?0\d{1,2}-\d{3,4}-\d{4}\)?",s))
    if not pm:return ""
    p=pm[-1]
    before=s[:p.start()].strip()
    for marker in ("간담회","업무협의","회의","협의","격려","오찬","만찬","소통"):
        idx=before.rfind(marker)
        if idx>=0 and idx+len(marker)<len(before):
            cand=before[idx+len(marker):].strip(" -·,")
            if 1<len(cand)<=50:return cand
    # Conservative fallback: take the final contiguous merchant-like phrase.
    m=re.search(r"([가-힣A-Za-z0-9㈜&·\s]{2,24})$",before)
    return " ".join(m.group(1).split()) if m else ""

def _parse_pdf(att:dict):
    try:
        from pypdf import PdfReader
        blob=fetch(att["url"],att.get("parent",""))
        pdf=PdfReader(io.BytesIO(blob))
    except Exception as e:return [],f"pdf {att['url']}: {type(e).__name__}: {e}"
    rows=[]
    for pi,page in enumerate(pdf.pages,start=1):
        raw=page.extract_text() or ""
        hm=re.search(r"20\d{2}년\s*\d{1,2}월\s*(기관장|임원)\s*업무추진비",raw)
        role=hm.group(1) if hm else ""
        if not role:continue
        compact=" ".join(raw.split())
        starts=list(re.finditer(r"20\d{2}[.]\d{1,2}[.]\d{1,2}[.]?",compact))
        for idx,m in enumerate(starts):
            seg=compact[m.start():(starts[idx+1].start() if idx+1<len(starts) else len(compact))]
            date=_norm_date(seg)
            if not date:continue
            amount_m=re.search(r"(\d{1,3}(?:,\d{3})+|\d{4,})\s*(?:계|$)",seg)
            if not amount_m:
                amount_m=re.search(r"(\d{1,3}(?:,\d{3})+|\d{4,})\s*$",seg)
            amount=int(amount_m.group(1).replace(",","")) if amount_m else None
            method_m=re.search(r"(계좌이체|법인카드|카드|현금)\s*(\d{1,2})",seg)
            method=method_m.group(1) if method_m else ""
            people=int(method_m.group(2)) if method_m else None
            merchant=_merchant_from_prefix(seg)
            if not merchant:continue
            # Purpose is retained as the transaction segment minus date and trailing columns.
            purpose=seg[m.end()-m.start():]
            phone_pos=re.search(r"\(?0\d{1,2}-\d{3,4}-\d{4}\)?",purpose)
            if phone_pos:purpose=purpose[:phone_pos.start()]
            purpose=" ".join(purpose.split())
            rows.append({
                "source_key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
                "role":role,"department":"","used_date":date,"used_time":"",
                "merchant":merchant,"address":"","purpose":purpose,
                "people":people,"amount":amount,"source_amount_scale":1,
                "payment_method":method,"source_category":role,"target":"",
                "source_url":att["url"],"source_sheet":f"page-{pi}","source_row":idx+1,
                "row_id":f"fira:{att['attachment_id']}:{pi}:{idx+1}",
            })
    return rows,None

def discover(year:int)->dict:
    attachments,pages,errors=_discover_files(year);rows=[]
    if attachments:
        with ThreadPoolExecutor(max_workers=min(5,len(attachments))) as pool:
            fm={pool.submit(_parse_pdf,a):a for a in attachments}
            for fut in as_completed(fm):
                parsed,err=fut.result();rows.extend(parsed)
                if err:errors.append(err)
    rows.sort(key=lambda r:(r["used_date"],r["role"],r["row_id"]))
    return {
        "key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
        "default_role":"기관장·임원","years":[year-1,year],"pages":pages,
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
        "roles":sorted({r["role"] for r in fresh["inline_rows"]}),
        "errors":fresh["errors"][:8],
    },ensure_ascii=False))

if __name__=="__main__":main()
