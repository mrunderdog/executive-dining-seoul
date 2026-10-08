#!/usr/bin/env python3
from __future__ import annotations

import html, io, json, re, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from ingest_central_executive_expense import rows_from

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="hrdk"
INSTITUTION="한국산업인력공단"
BOARDS=[
    ("이사장","https://www.hrdkorea.or.kr/7/5/5/10/1"),
    ("임원","https://www.hrdkorea.or.kr/7/5/5/10/2"),
]
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

def fetch(url:str,binary:bool=False,referer:str=""):
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={
                "User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9",
                "Referer":referer or url,"Connection":"close",
            })
            with urllib.request.urlopen(req,timeout=20) as r:
                raw=r.read()
                if binary:return raw
                enc=r.headers.get_content_charset() or "euc-kr"
                return raw.decode(enc,"replace")
        except Exception as e:
            last=e
            if attempt<2:time.sleep(1+attempt)
    raise last

def clean(v): return " ".join(str(v or "").replace("\n"," ").split())

def to_int(v):
    s=re.sub(r"[^0-9.-]","",str(v or ""))
    try:return int(round(float(s)))
    except Exception:return None

def norm_date(v):
    s=clean(v)
    m=re.search(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})",s)
    if not m:return ""
    try:return datetime(*map(int,m.groups())).date().isoformat()
    except ValueError:return ""

def discover_files(year:int):
    years={year,year-1}; files=[]; pages=[]; errors=[]
    for board_role,base in BOARDS:
        for page_no in range(1,16):
            u=base+("?pageNo="+str(page_no) if page_no>1 else "")
            try:doc=fetch(u)
            except Exception as e:
                errors.append(f"listing {u}: {type(e).__name__}: {e}");continue
            pages.append(u)
            page_years=[]
            found=0
            for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
                txt=clean(html.unescape(re.sub(r"<[^>]+>"," ",row)))
                ym=re.search(r"(20\d{2})년\s*(\d{1,2})월\s*([^\n]*?)업무추진비\s*집행\s*내역",txt)
                if not ym:continue
                y,mo=int(ym.group(1)),int(ym.group(2)); page_years.append(y)
                if y not in years:continue
                hm=re.search(r'href=["\']([^"\']*\?k=(\d+)[^"\']*)["\']',row,re.I)
                if not hm:continue
                detail=urllib.parse.urljoin(u,html.unescape(hm.group(1)).replace("&amp;","&"))
                title=clean(html.unescape(re.sub(r"<[^>]+>"," ",re.search(r"<a\b[^>]*>.*?</a>",row,re.I|re.S).group(0)))) if re.search(r"<a\b[^>]*>.*?</a>",row,re.I|re.S) else txt
                try:ddoc=fetch(detail)
                except Exception as e:
                    errors.append(f"detail {detail}: {type(e).__name__}: {e}");continue
                pages.append(detail)
                am=re.search(r"<a\\b[^>]*href=['\"][^'\"]*/cms/download/downloadFile\\.hrd\\?attachSeq=(\\d+)[^'\"]*['\"][^>]*>(.*?)</a>",ddoc,re.I|re.S)
                if am:
                    aid=am.group(1)
                    file_name=clean(html.unescape(re.sub(r"<[^>]+>"," ",am.group(2))))
                else:
                    sm=re.search(r'/cms/download/downloadFile\\.hrd\\?attachSeq=(\\d+)',ddoc,re.I)
                    if not sm:continue
                    aid=sm.group(1)
                    file_name=title
                dl=f"https://www.hrdkorea.or.kr/cms/download/downloadFile.hrd?attachSeq={aid}"
                role_m=re.search(r"(이사장|상임감사|기획운영이사|능력개발이사|능력평가이사|국제인력본부장|[^\s]+이사)\s*업무추진비",title)
                role=role_m.group(1) if role_m else board_role
                files.append({
                    "year":y,"month":mo,"role":role,"text":title,
                    "url":dl,"download_url":dl,"parent":detail,
                    "attachment_id":aid,"filename":file_name,
                })
                found+=1
            if page_years and min(page_years)<min(years):break
            if page_no>1 and found==0 and not page_years:break
    uniq={x["attachment_id"]:x for x in files}
    return sorted(uniq.values(),key=lambda x:(x["year"],x["month"],x["role"])),list(dict.fromkeys(pages)),errors

def parse_document(att):
    try:blob=fetch(att["url"],True,att.get("parent",""))
    except Exception as e:return [],f"download {att['url']}: {type(e).__name__}: {e}"
    rows=[]
    try:
        file_name=att.get("filename") or att.get("text") or "expense.pdf"
        for sheet,table in rows_from(blob,file_name):
            if not table:continue
            header=None
            for hi,cells in enumerate(table):
                vals=[clean(x) for x in (cells or [])]
                normalized=[v.replace(" ","") for v in vals]
                if ("집행일자" in normalized or "사용일자" in normalized) and any("사용처" in x for x in normalized):
                    header=(hi,normalized);break
            if header is None:continue
            hi,hdr=header
            def idx_contains(*keys):
                for i,h in enumerate(hdr):
                    if any(k in h for k in keys):return i
                return None
            di=idx_contains("집행일자","사용일자")
            mi=idx_contains("사용처")
            pi_i=idx_contains("집행내역","집행목적","사용목적","목적","내역")
            ri_i=idx_contains("집행자","사용자","직위")
            ti_i=idx_contains("집행대상자","대상")
            pay_i=idx_contains("집행구분","결제방법","결제수단")
            people_i=idx_contains("인원")
            amount_i=idx_contains("집행금액","사용금액","금액")
            if None in (di,mi,amount_i):continue
            def get(vals,i): return vals[i] if i is not None and i<len(vals) else ""
            for ri,cells in enumerate(table[hi+1:],start=hi+2):
                vals=[clean(x) for x in (cells or [])]
                d=norm_date(get(vals,di)); merchant=get(vals,mi).strip()
                if not d or not merchant or merchant in {"-","사용처(장소)","사용처","계","합계"}:continue
                role=get(vals,ri_i).strip() or att["role"]
                rows.append({
                    "source_key":KEY,"institution":INSTITUTION,
                    "cohort":"public_enterprise_leadership",
                    "role":role,"department":"","used_date":d,"used_time":"",
                    "merchant":merchant,"address":"","purpose":get(vals,pi_i),
                    "target":get(vals,ti_i),"payment_method":get(vals,pay_i),
                    "people":to_int(get(vals,people_i)),"amount":to_int(get(vals,amount_i)),
                    "source_amount_scale":1,"source_category":att["role"],
                    "source_url":att["url"],"source_sheet":sheet,
                    "source_row":ri,
                    "row_id":f"hrdk:{att['attachment_id']}:{sheet}:{ri}",
                })
    except Exception as e:
        return [],f"parse {att['url']}: {type(e).__name__}: {e}"
    return rows,None

def discover(year:int):
    attachments,pages,errors=discover_files(year); rows=[]
    if attachments:
        with ThreadPoolExecutor(max_workers=min(8,len(attachments))) as pool:
            fm={pool.submit(parse_document,a):a for a in attachments}
            for fut in as_completed(fm):
                parsed,err=fut.result(); rows.extend(parsed)
                if err:errors.append(err)
    rows.sort(key=lambda r:(r["used_date"],r["role"],r["row_id"]))
    return {
        "key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
        "default_role":"이사장·상임감사·상임이사","years":[year-1,year],
        "pages":pages,"attachments":attachments,"inline_rows":rows,
        "inline_replace":True,"errors":errors,"parseable_attachments":len(attachments),
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
