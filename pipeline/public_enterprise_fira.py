#!/usr/bin/env python3
from __future__ import annotations

import html, io, json, re, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import pdfplumber

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="fira"
INSTITUTION="한국수산자원공단"
BASE="https://www.fira.or.kr/newfira/web/info/info02_02.jsp"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def fetch(url:str,binary:bool=False,referer:str=""):
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9","Referer":referer or url,"Connection":"close"})
            with urllib.request.urlopen(req,timeout=20) as r:
                raw=r.read()
                return raw if binary else raw.decode(r.headers.get_content_charset() or "utf-8","replace")
        except Exception as e:
            last=e
            if attempt<2: time.sleep(1.0+attempt)
    raise last

def clean(v): return " ".join(str(v or "").replace("\n"," ").split())

def date_norm(v):
    m=re.search(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})",clean(v))
    if not m:return ""
    try:return datetime(*map(int,m.groups())).date().isoformat()
    except ValueError:return ""

def to_int(v):
    s=re.sub(r"[^0-9.-]","",str(v or ""))
    try:return int(round(float(s)))
    except Exception:return None

def merchant_clean(v):
    s=clean(v)
    s=re.sub(r"\s*\((?:0\d{1,3}|0507)[-\d]+\)\s*$","",s)
    return s.strip()

def discover_files(year:int):
    years={year,year-1}; files=[]; pages=[]; errors=[]
    urls=[BASE+"?board_no=186&board_wrapper=%2Fnewfira%2Fweb%2Finfo%2Finfo02_02.jsp&mode=list&pager.offset="+str(o) for o in range(0,71,10)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        fm={pool.submit(fetch,u):u for u in urls}
        for fut in as_completed(fm):
            u=fm[fut]
            try:doc=fut.result()
            except Exception as e:
                errors.append(f"listing {u}: {type(e).__name__}: {e}");continue
            pages.append(u)
            for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
                txt=clean(html.unescape(re.sub(r"<[^>]+>"," ",row)))
                ym=re.search(r"기관장\s*및\s*임원\s*업무추진비성\s*경비내역\s*\((20\d{2})년\s*(\d{1,2})월\)",txt)
                if not ym or int(ym.group(1)) not in years:continue
                hm=re.search(r"href=['\"]([^'\"]*article_no=(\d+)[^'\"]*)['\"]",row,re.I)
                if not hm:continue
                detail=urllib.parse.urljoin(u,html.unescape(hm.group(1)))
                try:ddoc=fetch(detail)
                except Exception as e:
                    errors.append(f"detail {detail}: {type(e).__name__}: {e}");continue
                pages.append(detail)
                am=re.search(r"fira\.jsp\?attach_no=(\d+)",ddoc,re.I)
                if not am:continue
                aid=am.group(1)
                dl=f"https://www.fira.or.kr/_custom/cms/_common/board/fira.jsp?attach_no={aid}"
                files.append({"year":int(ym.group(1)),"month":int(ym.group(2)),"url":dl,"download_url":dl,"parent":detail,"attachment_id":aid,"text":txt})
    uniq={x["attachment_id"]:x for x in files}
    return sorted(uniq.values(),key=lambda x:(x["year"],x["month"])),pages,errors

def parse_pdf(att):
    try:blob=fetch(att["url"],True,att.get("parent",""))
    except Exception as e:return [],f"download {att['url']}: {type(e).__name__}: {e}"
    rows=[]
    try:
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            for pi,page in enumerate(pdf.pages,1):
                ptext=page.extract_text() or ""
                role="기관장" if "기관장 업무추진비" in ptext else ("임원" if "임원 업무추진비" in ptext else "")
                if not role:continue
                for ti,table in enumerate(page.extract_tables(),1):
                    for ri,cells in enumerate(table or [],1):
                        if len(cells or [])<7:continue
                        d=date_norm(cells[0])
                        if not d:continue
                        merchant=merchant_clean(cells[2])
                        if not merchant or merchant in {"-","사용처(장소)"}:continue
                        rows.append({
                            "source_key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
                            "role":role,"department":"","used_date":d,"used_time":"",
                            "merchant":merchant,"address":"","purpose":clean(cells[1]),
                            "target":clean(cells[3]),"payment_method":clean(cells[4]),
                            "people":to_int(cells[5]),"amount":to_int(cells[6]),
                            "source_amount_scale":1,"source_category":role,
                            "source_url":att["url"],"source_sheet":f"p{pi}-t{ti}","source_row":ri,
                            "row_id":f"fira:{att['attachment_id']}:p{pi}:t{ti}:r{ri}",
                        })
    except Exception as e:
        return [],f"parse {att['url']}: {type(e).__name__}: {e}"
    return rows,None

def discover(year:int):
    attachments,pages,errors=discover_files(year); rows=[]
    if attachments:
        with ThreadPoolExecutor(max_workers=min(6,len(attachments))) as pool:
            fm={pool.submit(parse_pdf,a):a for a in attachments}
            for fut in as_completed(fm):
                parsed,err=fut.result();rows.extend(parsed)
                if err:errors.append(err)
    rows.sort(key=lambda r:(r["used_date"],r["role"],r["row_id"]))
    return {"key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
            "default_role":"기관장·임원","years":[year-1,year],"pages":list(dict.fromkeys(pages)),
            "attachments":attachments,"inline_rows":rows,"inline_replace":True,
            "errors":errors,"parseable_attachments":len(attachments),
            "status":"PARSEABLE_FOUND" if rows else ("FETCH_FAILED" if errors else "NO_FILES_FOUND")}

def main():
    payload=json.loads(REPORT.read_text(encoding="utf-8"))
    fresh=discover(int(payload.get("year") or datetime.now().year))
    payload["sources"]=[x for x in payload.get("sources",[]) if x.get("key")!=KEY]+[fresh]
    REPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"key":KEY,"status":fresh["status"],"attachments":len(fresh["attachments"]),"rows":len(fresh["inline_rows"]),
                      "merchants":len({r["merchant"] for r in fresh["inline_rows"]}),"roles":sorted({r["role"] for r in fresh["inline_rows"]}),
                      "date_min":min((r["used_date"] for r in fresh["inline_rows"]),default=""),"date_max":max((r["used_date"] for r in fresh["inline_rows"]),default=""),
                      "errors":fresh["errors"][:8]},ensure_ascii=False))
if __name__=="__main__":main()
