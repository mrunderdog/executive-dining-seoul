#!/usr/bin/env python3
from __future__ import annotations

import html, io, json, re, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="keco"
INSTITUTION="한국환경공단"
LISTING="https://www.keco.or.kr/web/lay1/bbs/S1T106C997/A/52/list.do"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def fetch(url:str,referer:str="")->bytes:
    req=urllib.request.Request(url,headers={
        "User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9","Referer":referer or LISTING,
    })
    with urllib.request.urlopen(req,timeout=20) as r:return r.read()

def text_fetch(url:str)->str:
    raw=fetch(url)
    for enc in ("utf-8","cp949","euc-kr"):
        try:return raw.decode(enc)
        except Exception:pass
    return raw.decode("utf-8","replace")

def _date(v,datemode=0)->str:
    if isinstance(v,(int,float)) and 30000<=float(v)<=60000:
        return (datetime(1899,12,30)+timedelta(days=float(v))).date().isoformat()
    s=" ".join(str(v or "").split())
    try:
        n=float(s)
        if 30000<=n<=60000:
            return (datetime(1899,12,30)+timedelta(days=n)).date().isoformat()
    except Exception:pass
    m=re.search(r"(20\d{2})[-./년\s]+(\d{1,2})[-./월\s]+(\d{1,2})",s)
    if not m:return ""
    try:return datetime(*map(int,m.groups())).date().isoformat()
    except ValueError:return ""

def _int(v):
    try:return int(round(float(str(v or "").replace(",","").strip())))
    except Exception:return None

def _discover_files(year:int):
    years={year,year-1}; files=[]; pages=[]; errors=[]
    for page in range(1,6):
        u=LISTING+("?cpage="+str(page)+"&rows=10&condition=&keyword=" if page>1 else "")
        try:doc=text_fetch(u)
        except Exception as e:
            errors.append(f"listing {u}: {type(e).__name__}: {e}");continue
        pages.append(u)
        page_years=[]
        for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
            txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
            ym=re.search(r"(20\d{2})년\s*(\d{1,2})월\s*임원\s*업무추진비",txt)
            if not ym:continue
            y,m=int(ym.group(1)),int(ym.group(2));page_years.append(y)
            if y not in years:continue
            dm=re.search(r'href=["\']([^"\']*view\.do\?[^"\']*article_seq=\d+[^"\']*)["\']',row,re.I)
            if not dm:continue
            detail=urllib.parse.urljoin(u,html.unescape(dm.group(1)).replace("&amp;","&"))
            try:ddoc=text_fetch(detail)
            except Exception as e:
                errors.append(f"detail {detail}: {type(e).__name__}: {e}");continue
            pages.append(detail)
            fm=re.search(r'href=["\'](/download\.do\?uuid=([^"\']+\.xls))["\']',ddoc,re.I)
            if not fm:continue
            dl=urllib.parse.urljoin(detail,html.unescape(fm.group(1)))
            files.append({
                "text":txt,"url":dl,"download_url":dl,"parent":detail,
                "year":y,"month":m,"attachment_id":fm.group(2),
            })
        if page_years and min(page_years)<min(years):break
    uniq={x["attachment_id"]:x for x in files}
    return sorted(uniq.values(),key=lambda x:(x["year"],x["month"])),list(dict.fromkeys(pages)),errors

def _parse_xls(att:dict):
    try:
        import xlrd
        blob=fetch(att["url"],att.get("parent",""))
        book=xlrd.open_workbook(file_contents=blob)
    except Exception as e:return [],f"xls {att['url']}: {type(e).__name__}: {e}"
    rows=[]
    for si in range(book.nsheets):
        sh=book.sheet_by_index(si)
        if sh.name=="요약":continue
        header=None
        for ri in range(sh.nrows):
            vals=[sh.cell_value(ri,ci) for ci in range(sh.ncols)]
            texts=[" ".join(str(v or "").split()) for v in vals]
            if "사용일자" in texts and "집행자" in texts and "사용처(장소)" in texts:
                header={name:texts.index(name) for name in ("사용일자","집행자","집행내역","사용처(장소)","집행대상자","집행구분","인원","집행금액") if name in texts}
                continue
            if not header:continue
            def get(name):
                i=header.get(name)
                return vals[i] if i is not None and i<len(vals) else ""
            date=_date(get("사용일자"),book.datemode)
            merchant=" ".join(str(get("사용처(장소)") or "").split()).strip()
            role=" ".join(str(get("집행자") or "").split()).strip()
            if not date or not merchant or merchant in {"-","사용처(장소)","사용처"}:continue
            rows.append({
                "source_key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
                "role":role or "임원","department":"","used_date":date,"used_time":"",
                "merchant":merchant,"address":"","purpose":" ".join(str(get("집행내역") or "").split()),
                "target":" ".join(str(get("집행대상자") or "").split()),
                "payment_method":" ".join(str(get("집행구분") or "").split()),
                "people":_int(get("인원")),"amount":_int(get("집행금액")),
                "source_amount_scale":1,"source_category":"임원",
                "source_url":att["url"],"source_sheet":sh.name,"source_row":ri+1,
                "row_id":f"keco:{att['attachment_id']}:{sh.name}:{ri+1}",
            })
    return rows,None

def discover(year:int)->dict:
    attachments,pages,errors=_discover_files(year); rows=[]
    if attachments:
        with ThreadPoolExecutor(max_workers=min(5,len(attachments))) as pool:
            fm={pool.submit(_parse_xls,a):a for a in attachments}
            for fut in as_completed(fm):
                parsed,err=fut.result();rows.extend(parsed)
                if err:errors.append(err)
    rows.sort(key=lambda r:(r["used_date"],r["role"],r["row_id"]))
    return {
        "key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
        "default_role":"이사장·감사·상임이사","years":[year-1,year],
        "pages":pages,"attachments":attachments,"inline_rows":rows,"inline_replace":True,
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
        "rows":len(fresh["inline_rows"]),"merchants":len({r["merchant"] for r in fresh["inline_rows"]}),
        "roles":sorted({r["role"] for r in fresh["inline_rows"]}),
        "date_min":min((r["used_date"] for r in fresh["inline_rows"]),default=""),
        "date_max":max((r["used_date"] for r in fresh["inline_rows"]),default=""),
        "errors":fresh["errors"][:8],
    },ensure_ascii=False))

if __name__=="__main__":main()
