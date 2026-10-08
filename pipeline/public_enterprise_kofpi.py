#!/usr/bin/env python3
from __future__ import annotations

import html, io, json, re, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import xlrd

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="kofpi"
INSTITUTION="한국임업진흥원"
BASE="https://www.kofpi.or.kr"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

SOURCES=[
    ("25","기관장","기관장"),
    ("26","임원","임원"),
]

def request(url:str,data:bytes|None=None,referer:str=""):
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,data=data,headers={
                "User-Agent":UA,"Accept":"*/*","Accept-Language":"ko-KR,ko;q=0.9",
                "Referer":referer or url,
                **({"Content-Type":"application/x-www-form-urlencoded"} if data is not None else {}),
            })
            with urllib.request.urlopen(req,timeout=20) as r:
                return r.read(),r.geturl(),r.headers
        except Exception as e:
            last=e
            if attempt<2: time.sleep(1+attempt)
    raise last

def fetch_text(url:str,data:bytes|None=None,referer:str="")->str:
    raw,_,h=request(url,data,referer)
    return raw.decode(h.get_content_charset() or "utf-8","replace")

def norm_date(v,datemode=0):
    if isinstance(v,(int,float)) and 30000<=float(v)<=60000:
        return (datetime(1899,12,30)+timedelta(days=float(v))).date().isoformat()
    s=" ".join(str(v or "").split())
    try:
        n=float(s)
        if 30000<=n<=60000:
            return (datetime(1899,12,30)+timedelta(days=n)).date().isoformat()
    except Exception: pass
    m=re.search(r"(20\d{2})[-./년\s]+(\d{1,2})[-./월\s]+(\d{1,2})",s)
    if not m:return ""
    try:return datetime(*map(int,m.groups())).date().isoformat()
    except ValueError:return ""

def to_int(v):
    s=re.sub(r"[^0-9.-]","",str(v or ""))
    try:return int(round(float(s)))
    except Exception:return None

def discover_files(year:int):
    years={year,year-1}; files=[]; pages=[]; errors=[]
    for sub,kind,default_role in SOURCES:
        for page in range(1,5):
            list_url=f"{BASE}/public/publicInfo_03_001.do?"+urllib.parse.urlencode({"sub":sub,"cPage":page})
            try:doc=fetch_text(list_url)
            except Exception as e:
                errors.append(f"listing {list_url}: {type(e).__name__}: {e}");continue
            pages.append(list_url)
            found_years=[]
            for row in re.findall(r"<tr\b.*?</tr>",doc,re.I|re.S):
                txt=" ".join(html.unescape(re.sub(r"<[^>]+>"," ",row)).split())
                if sub=="25":
                    ym=re.search(r"(20\d{2})년\s*기관장\s*업무추진비\s*집행내역\((\d{1,2})월\)",txt)
                else:
                    ym=re.search(r"(20\d{2})년\s*임원\s*업무추진비\s*집행내역\((\d{1,2})월\)",txt)
                if not ym:continue
                y,mo=int(ym.group(1)),int(ym.group(2));found_years.append(y)
                if y not in years:continue
                sm=re.search(r"fnGoView\(['\"](\d+)['\"]\)",row,re.I)
                if not sm:continue
                seq=sm.group(1)
                view_url=f"{BASE}/public/publicInfo_03_001view.do"
                post=urllib.parse.urlencode({"cPage":str(page),"bb_seq":seq,"subtype":sub}).encode()
                try:ddoc=fetch_text(view_url,post,list_url)
                except Exception as e:
                    errors.append(f"detail {seq}: {type(e).__name__}: {e}");continue
                pages.append(f"{view_url}?bb_seq={seq}&subtype={sub}")
                am=re.search(r"fnNotiDownload\(['\"](\d+)['\"]\)",ddoc,re.I)
                if not am:continue
                file_seq=am.group(1)
                files.append({
                    "year":y,"month":mo,"kind":kind,"default_role":default_role,
                    "sub":sub,"seq":seq,"file_seq":file_seq,
                    "text":txt,"parent":f"{view_url}?bb_seq={seq}&subtype={sub}",
                    "url":f"{BASE}/noti/download.do","download_url":f"{BASE}/noti/download.do",
                    "attachment_id":f"{sub}|{seq}|{file_seq}",
                })
            if found_years and min(found_years)<min(years):
                break
    uniq={x["attachment_id"]:x for x in files}
    return sorted(uniq.values(),key=lambda x:(x["year"],x["month"],x["sub"])),list(dict.fromkeys(pages)),errors

def download(att):
    data=urllib.parse.urlencode({"fileSeq":att["file_seq"]}).encode()
    blob,_,_=request(att["url"],data,att.get("parent",""))
    return blob

def parse_xls(att):
    try:
        blob=download(att)
        book=xlrd.open_workbook(file_contents=blob)
    except Exception as e:
        return [],f"xls {att['file_seq']}: {type(e).__name__}: {e}"
    rows=[]
    for si in range(book.nsheets):
        sh=book.sheet_by_index(si)
        if sh.nrows==0:continue
        header=None
        inferred_role=att["default_role"]
        for ri in range(min(sh.nrows,8)):
            first=" ".join(str(sh.cell_value(ri,0) or "").split())
            rm=re.search(r"업무추진비\(([^)]+)\)",first)
            if rm: inferred_role=rm.group(1).strip()
        for ri in range(sh.nrows):
            vals=[sh.cell_value(ri,ci) for ci in range(sh.ncols)]
            texts=[" ".join(str(v or "").split()) for v in vals]
            if "사용일자" in texts and "사용처(장소)" in texts:
                names=("사용일자","집행자","집 행 내 역(목 적)","집행내역(목적)","사용처(장소)","집행대상자","집행구분","인원(명)","집행금액(원)")
                header={}
                for n in names:
                    if n in texts:header[n]=texts.index(n)
                continue
            if not header:continue
            def get(*names):
                for n in names:
                    i=header.get(n)
                    if i is not None and i<len(vals):return vals[i]
                return ""
            d=norm_date(get("사용일자"),book.datemode)
            merchant=" ".join(str(get("사용처(장소)") or "").split()).strip()
            if not d or not merchant or merchant in {"-","사용처(장소)","해당없음"}:continue
            role=" ".join(str(get("집행자") or "").split()).strip()
            if not role or role=="-":role=inferred_role
            purpose=" ".join(str(get("집 행 내 역(목 적)","집행내역(목적)") or "").split())
            rows.append({
                "source_key":KEY,"institution":INSTITUTION,
                "cohort":"public_enterprise_leadership",
                "role":role,"department":"",
                "used_date":d,"used_time":"",
                "merchant":merchant,"address":"",
                "purpose":purpose,
                "target":" ".join(str(get("집행대상자") or "").split()),
                "payment_method":" ".join(str(get("집행구분") or "").split()),
                "people":to_int(get("인원(명)")),"amount":to_int(get("집행금액(원)")),
                "source_amount_scale":1,"source_category":att["kind"],
                "source_url":att["parent"],"source_sheet":sh.name,"source_row":ri+1,
                "row_id":f"kofpi:{att['attachment_id']}:{sh.name}:{ri+1}",
            })
    return rows,None

def discover(year:int):
    attachments,pages,errors=discover_files(year);rows=[]
    if attachments:
        with ThreadPoolExecutor(max_workers=min(6,len(attachments))) as pool:
            fm={pool.submit(parse_xls,a):a for a in attachments}
            for fut in as_completed(fm):
                parsed,err=fut.result();rows.extend(parsed)
                if err:errors.append(err)
    rows.sort(key=lambda r:(r["used_date"],r["role"],r["row_id"]))
    return {
        "key":KEY,"institution":INSTITUTION,"cohort":"public_enterprise_leadership",
        "default_role":"기관장·상임이사","years":[year-1,year],"pages":pages,
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
        "rows":len(fresh["inline_rows"]),"merchants":len({r["merchant"] for r in fresh["inline_rows"]}),
        "roles":sorted({r["role"] for r in fresh["inline_rows"]}),
        "date_min":min((r["used_date"] for r in fresh["inline_rows"]),default=""),
        "date_max":max((r["used_date"] for r in fresh["inline_rows"]),default=""),
        "errors":fresh["errors"][:8],
    },ensure_ascii=False))

if __name__=="__main__":main()
