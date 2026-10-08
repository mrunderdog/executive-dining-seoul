#!/usr/bin/env python3
from __future__ import annotations

import html, io, json, re, time, urllib.parse, urllib.request, zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"public-enterprise-discovery.json"
KEY="nia"
INSTITUTION="한국지능정보사회진흥원"
BASE="https://www.nia.or.kr"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36"

BOARDS=[
    ("원장","75636"),
    ("임원","24254"),
    ("본부장·실단장","62176"),
]

def fetch(url:str,binary:bool=False,referer:str=""):
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={
                "User-Agent":UA,
                "Accept":"*/*",
                "Accept-Language":"ko-KR,ko;q=0.9",
                "Referer":referer or BASE,
                "Connection":"close",
            })
            with urllib.request.urlopen(req,timeout=20) as r:
                raw=r.read()
                return raw if binary else raw.decode(r.headers.get_content_charset() or "utf-8","replace")
        except Exception as e:
            last=e
            if attempt<2: time.sleep(1+attempt)
    raise last

def clean(v):
    return " ".join(str(v or "").replace("\n"," ").split()).strip()

def local(tag):
    return tag.rsplit("}",1)[-1]

def cell_text(el):
    vals=[]
    for x in el.iter():
        if x.text and x.text.strip():
            vals.append(clean(x.text))
    return clean(" ".join(vals))

def parse_dt(v):
    s=clean(v)
    dm=re.search(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})",s)
    tm=re.search(r"(\d{1,2}):(\d{2})",s)
    d=""
    if dm:
        try:d=datetime(*map(int,dm.groups())).date().isoformat()
        except ValueError:pass
    t=f"{int(tm.group(1)):02d}:{int(tm.group(2)):02d}" if tm else ""
    return d,t

def to_int(v):
    s=re.sub(r"[^0-9.-]","",str(v or ""))
    try:return int(round(float(s)))
    except Exception:return None

def parse_hwpx(blob:bytes,att:dict):
    rows=[]
    try:z=zipfile.ZipFile(io.BytesIO(blob))
    except Exception as e:return [],f"zip {att['download_url']}: {type(e).__name__}: {e}"
    for name in z.namelist():
        if not (name.startswith("Contents/section") and name.endswith(".xml")):continue
        try:root=ET.fromstring(z.read(name))
        except Exception as e:return [],f"xml {name}: {type(e).__name__}: {e}"
        for tbl_idx,tbl in enumerate([x for x in root.iter() if local(x.tag)=="tbl"],1):
            trs=[x for x in tbl if local(x.tag)=="tr"]
            if not trs:
                trs=[x for x in tbl.iter() if local(x.tag)=="tr"]
            header=None
            for ri,tr in enumerate(trs,1):
                cells=[cell_text(x) for x in tr if local(x.tag)=="tc"]
                if not cells:
                    cells=[cell_text(x) for x in tr.iter() if local(x.tag)=="tc"]
                if not cells:continue
                if "직위" in cells and ("사용일시" in cells or "사용일자" in cells) and ("사용장소" in cells or "사용처(장소)" in cells):
                    header={v:i for i,v in enumerate(cells)}
                    continue
                if not header:continue
                def get(*names):
                    for n in names:
                        i=header.get(n)
                        if i is not None and i<len(cells):return cells[i]
                    return ""
                d,t=parse_dt(get("사용일시","사용일자"))
                merchant=clean(get("사용장소","사용처(장소)"))
                role=clean(get("직위")) or att["board_role"]
                if not d or not merchant or merchant in {"-","해당 월 집행내역 없음","해당없음"}:continue
                amount=to_int(get("사용금액","집행금액(원)"))
                people=to_int(get("인원(명)","대상인원(명)"))
                rows.append({
                    "source_key":KEY,"institution":INSTITUTION,
                    "cohort":"public_enterprise_leadership",
                    "role":role,"department":"",
                    "used_date":d,"used_time":t,
                    "merchant":merchant,"address":"",
                    "purpose":clean(get("사용목적","사용목적(내역)","집행내역(목적)")),
                    "target":clean(get("참석대상","집행대상자")),
                    "payment_method":clean(get("사용방법","집행구분")),
                    "people":people,"amount":amount,
                    "source_amount_scale":1,
                    "source_category":att["board_role"],
                    "source_url":att["download_url"],
                    "source_sheet":f"{name}:tbl{tbl_idx}",
                    "source_row":ri,
                    "row_id":f"nia:{att['cb_idx']}:{att['bc_idx']}:{att['file_no']}:{name}:t{tbl_idx}:r{ri}",
                })
    return rows,None

def discover_files(year:int):
    years={year,year-1};items=[];pages=[];errors=[]
    for board_role,cb_idx in BOARDS:
        for page in range(1,5):
            list_url=f"{BASE}/site/nia_kor/ex/bbs/List.do?"+urllib.parse.urlencode({"cbIdx":cb_idx,"pageIndex":page})
            try:doc=fetch(list_url)
            except Exception as e:
                errors.append(f"listing {list_url}: {type(e).__name__}: {e}");continue
            pages.append(list_url)
            page_years=[]
            pattern=re.compile(
                r'<a\b[^>]*onclick=["\']doBbsFView\(["\']'+re.escape(cb_idx)+
                r'["\'],["\'](\d+)["\'],["\'][^"\']*["\'],["\'](\d+)["\']\);return false;["\'][^>]*>(.*?)</a>',
                re.I|re.S
            )
            for m in pattern.finditer(doc):
                bc_idx,parent_seq,body=m.groups()
                title=clean(html.unescape(re.sub(r"<[^>]+>"," ",body)))
                ym=re.search(r"(20\d{2})년\s*(\d{1,2})월",title)
                if not ym:continue
                y,mo=int(ym.group(1)),int(ym.group(2));page_years.append(y)
                if y not in years:continue
                detail=f"{BASE}/site/nia_kor/ex/bbs/View.do?"+urllib.parse.urlencode({"cbIdx":cb_idx,"bcIdx":bc_idx,"parentSeq":parent_seq})
                try:ddoc=fetch(detail,referer=list_url)
                except Exception as e:
                    errors.append(f"detail {detail}: {type(e).__name__}: {e}");continue
                pages.append(detail)
                links=re.findall(r'href=["\']([^"\']*?/common/board/Download\.do\?[^"\']+)["\']',ddoc,re.I)
                for href in links:
                    dl=urllib.parse.urljoin(detail,html.unescape(href).replace("&amp;","&"))
                    qs=urllib.parse.parse_qs(urllib.parse.urlparse(dl).query)
                    file_no=(qs.get("fileNo") or ["1"])[0]
                    if not re.search(r"\.hwpx?(?:$|[?&])",ddoc,re.I):
                        # NIA current disclosures are HWPX; still keep download endpoint if filename is in surrounding HTML.
                        pass
                    items.append({
                        "board_role":board_role,"cb_idx":cb_idx,"bc_idx":bc_idx,"parent_seq":parent_seq,
                        "file_no":file_no,"year":y,"month":mo,"text":title,
                        "url":dl,"download_url":dl,"parent":detail,
                        "attachment_id":f"{cb_idx}|{bc_idx}|{file_no}",
                    })
                    break
            if page_years and min(page_years)<min(years):break
    uniq={x["attachment_id"]:x for x in items}
    return sorted(uniq.values(),key=lambda x:(x["year"],x["month"],x["cb_idx"],x["bc_idx"])),list(dict.fromkeys(pages)),errors

def parse_attachment(att):
    try:blob=fetch(att["download_url"],True,att.get("parent",""))
    except Exception as e:return [],f"download {att['download_url']}: {type(e).__name__}: {e}"
    if not blob.startswith(b"PK"):
        return [],f"download {att['download_url']}: unexpected payload {blob[:16]!r}"
    return parse_hwpx(blob,att)

def discover(year:int):
    attachments,pages,errors=discover_files(year);rows=[]
    if attachments:
        with ThreadPoolExecutor(max_workers=min(8,len(attachments))) as pool:
            fm={pool.submit(parse_attachment,a):a for a in attachments}
            for fut in as_completed(fm):
                parsed,err=fut.result();rows.extend(parsed)
                if err:errors.append(err)
    rows.sort(key=lambda r:(r["used_date"],r["role"],r["row_id"]))
    return {
        "key":KEY,"institution":INSTITUTION,
        "cohort":"public_enterprise_leadership",
        "default_role":"원장·임원·본부장·실단장",
        "years":[year-1,year],
        "pages":pages,"attachments":attachments,
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

if __name__=="__main__":main()
