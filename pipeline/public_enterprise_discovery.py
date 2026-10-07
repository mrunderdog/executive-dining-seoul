#!/usr/bin/env python3
from __future__ import annotations
import argparse, html, json, re, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from komipo_adapter import discover_komipo
from public_enterprise_hf import discover as discover_hf
from public_enterprise_hug import discover as discover_hug
from public_enterprise_ksure import discover as discover_ksure
from public_enterprise_nps import discover as discover_nps

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"sources"/"public_enterprise_registry.json"
KDHC_SNAPSHOT=ROOT/"sources"/"kdhc_executive_expense_snapshot.json"
REPORTS=ROOT/"reports"
UA="ExecutiveDiningSeoul/2.1 (+https://github.com/mrunderdog/executive-dining-seoul)"
FILE_EXTS=(".xlsx",".xls",".csv",".pdf",".hwp",".hwpx")

class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.anchors=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag.lower()=="a":
            self.stack.append({"href":attrs.get("href",""),"onclick":attrs.get("onclick",""),"title":attrs.get("title",""),"text":[]})
        elif self.stack and tag.lower()=="img":
            for k in ("alt","title"):
                if attrs.get(k):self.stack[-1]["text"].append(attrs[k])
    def handle_data(self,data):
        if self.stack:self.stack[-1]["text"].append(data)
    def handle_endtag(self,tag):
        if tag.lower()=="a" and self.stack:
            x=self.stack.pop();x["text"]=" ".join(" ".join([x.get("title",""),*x["text"]]).split());self.anchors.append(x)

def decode(raw,charset=None):
    for c in (charset,"utf-8","cp949","euc-kr"):
        if not c:continue
        try:return raw.decode(c)
        except Exception:pass
    return raw.decode("utf-8",errors="replace")

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,*/*;q=0.8"})
    with urllib.request.urlopen(req,timeout=35) as r:return decode(r.read(),r.headers.get_content_charset())

def onclick_url(base,value):
    if not value:return None
    for raw in re.findall(r"['\"]([^'\"]+)['\"]",html.unescape(value)):
        if any(x in raw.lower() for x in ("download","file","attach",".do",".jsp")):
            return urllib.parse.urljoin(base,raw)
    return None

def parse_links(base,doc):
    p=AnchorParser();p.feed(doc);out=[];seen=set()
    for a in p.anchors:
        href=html.unescape(a.get("href","")).strip();url=None
        if href and href!="#" and not href.lower().startswith("javascript:"):url=urllib.parse.urljoin(base,href)
        else:url=onclick_url(base,a.get("onclick",""))
        if not url or url in seen:continue
        seen.add(url);out.append({"text":a.get("text",""),"url":url})
    return out

def looks_file(x):
    s=(x.get("text","")+" "+x.get("url","")).lower()
    return any(ext in s for ext in FILE_EXTS) or any(t in s for t in ("download","filedown","attach","atchfile"))

def relevant_detail(x,years):
    s=(x.get("text","")+" "+x.get("url",""))
    # Institution-head disclosures use several titles across official sites.
    # Match standalone 사장 but not 부사장/본부장, which are separate cohorts.
    head_title=("기관장" in s or "사장직무대행" in s or re.search(r"(^|[^부본])사장(?:\s|업무|직무|$)",s))
    return bool(head_title) and any(str(y) in s for y in years)


def listing_urls(src):
    bases=list(src.get("listing_urls") or [])
    pagination=src.get("pagination") or {}
    param=str(pagination.get("param") or "").strip()
    if not param:
        return bases
    start=max(1,int(pagination.get("start") or 1))
    end=max(start,int(pagination.get("end") or start))
    out=[]
    for base in bases:
        parsed=urllib.parse.urlsplit(base)
        query=dict(urllib.parse.parse_qsl(parsed.query,keep_blank_values=True))
        for page in range(start,end+1):
            q=dict(query);q[param]=str(page)
            out.append(urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urllib.parse.urlencode(q),parsed.fragment)))
    return out

def extract_year_month(text):
    m=re.search(r"(20\d{2})\D{0,4}(1[0-2]|0?[1-9])\s*월",text)
    if m:return int(m.group(1)),int(m.group(2))
    m=re.search(r"(?:^|[^0-9])(\d{2})\s*[년.'’]?\s*(1[0-2]|0?[1-9])\s*월",text)
    if m:return 2000+int(m.group(1)),int(m.group(2))
    return None,None

def discover_kepco(src,year):
    base=(src.get("listing_urls") or [""])[0]
    out={"key":src["key"],"institution":src["institution"],"cohort":src.get("cohort","public_enterprise_leadership"),"default_role":src.get("default_role","기관장"),"years":[year],"pages":[base],"attachments":[],"errors":[]}
    try:doc=fetch(base)
    except Exception as e:
        out["errors"].append(f"listing {base}: {type(e).__name__}: {e}")
        out["parseable_attachments"]=0;out["status"]="FETCH_FAILED";return out
    endpoint=urllib.parse.urljoin(base,"/c2r/FileDownload.do")
    seen=set()
    for tm in re.finditer(r'<strong class="title">(.*?)</strong>',doc,re.S|re.I):
        title=html.unescape(re.sub(r"<[^>]+>"," ",tm.group(1)))
        title=" ".join(title.split())
        window=doc[max(0,tm.start()-900):min(len(doc),tm.end()+5200)]
        # KEPCO puts role badge and JS download button in the same card.
        if "기관장" not in window or not re.search(r"(^|[^부본])사장\s*업무추진비",title):
            continue
        y,m=extract_year_month(title)
        if y and y!=year:continue
        call=re.search(r"G_FILE\.downloadFile\('([^']+)'\s*,\s*'([^']+)'\)",window)
        if not call:continue
        file_no,file_seq=call.group(1),call.group(2)
        ident=file_no+"|"+file_seq
        if ident in seen:continue
        seen.add(ident)
        stable_url=base+"#kepco-file-"+urllib.parse.quote(file_no,safe="")
        out["attachments"].append({
            "text":title+" .pdf","url":stable_url,"download_url":endpoint,"year":y,"month":m,"parent":base,
            "post_data":{"fileNo":file_no,"fileSeq":file_seq},
            "attachment_id":ident
        })
    out["parseable_attachments"]=len(out["attachments"])
    out["status"]="PARSEABLE_FOUND" if out["attachments"] else "NO_FILES_FOUND"
    return out

def discover_kogas(src,year,detail_limit):
    base=(src.get("listing_urls") or [""])[0]
    lookback=max(0,int(src.get("lookback_years",1)))
    years={year-i for i in range(lookback+1)}
    out={"key":src["key"],"institution":src["institution"],"cohort":src.get("cohort","public_enterprise_leadership"),"default_role":src.get("default_role","기관장"),"years":sorted(years),"pages":[base],"attachments":[],"errors":[]}
    pagination=src.get("pagination") or {}
    start=max(1,int(pagination.get("start") or 1))
    end=max(start,int(pagination.get("end") or 3))
    listing_pages=[]
    for page in range(start,end+1):
        parsed=urllib.parse.urlsplit(base)
        q=dict(urllib.parse.parse_qsl(parsed.query,keep_blank_values=True))
        q.update({"pageOffset":str((page-1)*10),"pageIndex":str(page),"pageSize":"10"})
        listing_pages.append(urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urllib.parse.urlencode(q),parsed.fragment)))
    listing_docs=[]
    with ThreadPoolExecutor(max_workers=min(3,len(listing_pages))) as pool:
        future_map={pool.submit(fetch,u):u for u in listing_pages}
        for fut in as_completed(future_map):
            u=future_map[fut]
            try:listing_docs.append((u,fut.result()));out["pages"].append(u)
            except Exception as e:out["errors"].append(f"listing {u}: {type(e).__name__}: {e}")
    if not listing_docs:
        out["parseable_attachments"]=0;out["status"]="FETCH_FAILED";return out

    posts=[]
    seen_posts=set()
    for listing,doc in listing_docs:
        for m in re.finditer(r'<a\s+href=["\']javascript:readPermissionChk\((\d+)\);["\'][^>]*>(.*?)</a>',doc,re.S|re.I):
            board_idx=m.group(1)
            text=html.unescape(re.sub(r"<[^>]+>"," ",m.group(2)))
            text=" ".join(text.split())
            if board_idx in seen_posts:continue
            if not any(str(y) in text for y in years) or "업무추진비" not in text:continue
            if "기관장" not in text:continue
            seen_posts.add(board_idx)
            y,month=extract_year_month(text)
            detail=urllib.parse.urljoin(base,f"/site/koGas/bbs/View.do?cbIdx=57&boardIdx={board_idx}&Key=1060101050000&pageOffset=0&pageIndex=1")
            posts.append((board_idx,text,y,month,detail))
    posts=sorted(posts,key=lambda x:((x[2] or 0),(x[3] or 0)),reverse=True)[:detail_limit]

    seen_files=set()
    def fetch_detail(post):
        board_idx,title,y,month,detail=post
        return post,fetch(detail)
    if posts:
        with ThreadPoolExecutor(max_workers=min(6,len(posts))) as pool:
            future_map={pool.submit(fetch_detail,p):p for p in posts}
            for fut in as_completed(future_map):
                post=future_map[fut]
                board_idx,title,y,month,detail=post
                out["pages"].append(detail)
                try:_,ddoc=fut.result()
                except Exception as e:
                    out["errors"].append(f"detail {detail}: {type(e).__name__}: {e}");continue
                # KOGAS publishes one file per executive. Publish only the institution-head file.
                for m in re.finditer(r'<a\s+href=["\']([^"\']*?/mgr/fileDownload\.do\?[^"\']+)["\'][^>]*class=["\'][^"\']*pu_file_txt[^"\']*["\'][^>]*>(.*?)</a>',ddoc,re.S|re.I):
                    href=html.unescape(m.group(1))
                    label=html.unescape(re.sub(r"<[^>]+>"," ",m.group(2)))
                    label=" ".join(label.split())
                    if "기관장" not in label:continue
                    if not re.search(r"\.xlsx?\b",label,re.I):continue
                    url=urllib.parse.urljoin(detail,href)
                    if url in seen_files:continue
                    seen_files.add(url)
                    fy,fm=extract_year_month(label)
                    out["attachments"].append({
                        "text":label,"url":url,"year":fy or y,"month":fm or month,"parent":detail,
                        "attachment_id":f"{board_idx}|{urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get('fileNo',[''])[0]}"
                    })

    out["parseable_attachments"]=len(out["attachments"])
    out["status"]="PARSEABLE_FOUND" if out["attachments"] else ("FETCH_FAILED" if out["errors"] else "NO_FILES_FOUND")
    return out


# K-water publishes the institution-head ledger directly as an HTML table,
# one stable page per calendar year (2024=head16, 2025=head17, ...).
def discover_kwater(src,year):
    lookback=max(0,int(src.get("lookback_years",1)))
    years=sorted({year-i for i in range(lookback+1)})
    out={
        "key":src["key"],"institution":src["institution"],
        "cohort":src.get("cohort","public_enterprise_leadership"),
        "default_role":src.get("default_role","기관장"),
        "years":years,"pages":[],"attachments":[],"inline_rows":[],"errors":[],
        "inline_replace":True
    }
    for y in years:
        page_no=y-2008
        if page_no < 1:continue
        url=f"https://www.kwater.or.kr/water/sub02/sub02/head/head{page_no:02d}Page.do"
        try:doc=fetch(url)
        except Exception as e:
            out["errors"].append(f"listing {url}: {type(e).__name__}: {e}");continue
        out["pages"].append(url)
        if not re.search(fr"{y}년\s*세부집행내역",doc,re.I):
            out["errors"].append(f"year marker missing: {url}");continue
        mt=re.search(r"<table\b.*?</table>",doc,re.I|re.S)
        if not mt:
            out["errors"].append(f"table missing: {url}");continue
        rows=re.findall(r"<tr\b.*?</tr>",mt.group(0),re.I|re.S)
        for ri,row in enumerate(rows[1:],start=2):
            cells=[]
            for cell_html in re.findall(r"<t[hd]\b.*?</t[hd]>",row,re.I|re.S):
                s=html.unescape(re.sub(r"<[^>]+>"," ",cell_html))
                cells.append(" ".join(s.split()))
            if len(cells)==8:
                _,date_text,purpose,merchant,target,method,people_text,amount_text=cells
            elif len(cells)==7:
                date_text,purpose,merchant,target,method,people_text,amount_text=cells
            else:
                continue
            dm=re.fullmatch(r"\s*(1[0-2]|0?[1-9])월\s*(3[01]|[12]?\d)일\s*",date_text)
            if not dm:continue
            try:
                used_date=datetime(y,int(dm.group(1)),int(dm.group(2))).date().isoformat()
            except ValueError:
                continue
            merchant=" ".join(merchant.split())
            if not merchant:continue
            try:
                amount_krw=int(round(float(amount_text.replace(",",""))*1000))
            except Exception:
                amount_krw=None
            pm=re.search(r"\d+",people_text or "")
            people_count=int(pm.group()) if pm else None
            out["inline_rows"].append({
                "source_key":src["key"],"institution":src["institution"],
                "cohort":src.get("cohort","public_enterprise_leadership"),
                "role":src.get("default_role","기관장"),"department":"",
                "used_date":used_date,"used_time":"","merchant":merchant,"address":"",
                "purpose":" ".join(purpose.split()),"people":people_count,
                "amount":amount_krw,"source_amount_scale":1000,
                "payment_method":" ".join(method.split()),"source_category":"",
                "source_url":url,"source_sheet":f"{y}년","source_row":ri,
                "target":" ".join(target.split())
            })
    out["parseable_attachments"]=len(out["pages"]) if out["inline_rows"] else 0
    out["status"]="PARSEABLE_FOUND" if out["inline_rows"] else ("FETCH_FAILED" if out["errors"] else "NO_FILES_FOUND")
    return out

def discover_kospo(src,year):
    base=(src.get("listing_urls") or [""])[0]
    lookback=max(0,int(src.get("lookback_years",2)))
    years=sorted({year-i for i in range(lookback+1)})
    out={"key":src["key"],"institution":src["institution"],"cohort":src.get("cohort","public_enterprise_leadership"),"default_role":src.get("default_role","사장"),"years":years,"pages":[base],"attachments":[],"errors":[]}
    try:doc=fetch(base)
    except Exception as e:
        out["errors"].append(f"listing {base}: {type(e).__name__}: {e}")
        out["parseable_attachments"]=0;out["status"]="FETCH_FAILED";return out
    dm=re.search(r'disclosureNo\s*:\s*"([^"]+)"',doc) or re.search(r'\$submissionNo\s*=\s*"?([0-9]+)',doc)
    if not dm:
        out["errors"].append("ALIO disclosureNo missing")
        out["parseable_attachments"]=0;out["status"]="NO_FILES_FOUND";return out
    disclosure=dm.group(1)
    seen=set()
    for fm in re.finditer(r'<option\s+value="([^"]+)">\s*([^<]+\.(?:xlsx?|xls))\s*</option>',doc,re.I):
        file_no,label=fm.group(1),html.unescape(fm.group(2)).strip()
        ym=re.search(r'(20\d{2})',label)
        if not ym:continue
        y=int(ym.group(1))
        if y not in years:continue
        url=f"https://www.alio.go.kr/download/file.json?d={disclosure}&f={file_no}"
        if url in seen:continue
        seen.add(url)
        out["attachments"].append({"text":label,"url":url,"download_url":url,"year":y,"month":None,"parent":base,"attachment_id":f"{disclosure}|{file_no}"})
    out["parseable_attachments"]=len(out["attachments"])
    out["status"]="PARSEABLE_FOUND" if out["attachments"] else "NO_FILES_FOUND"
    return out

def discover_kdhc(src,year):
    out={
        "key":src["key"],"institution":src["institution"],
        "cohort":src.get("cohort","public_enterprise_leadership"),
        "default_role":src.get("default_role","경영진"),
        "years":[year-1,year],"pages":list(src.get("listing_urls") or []),
        "attachments":[],"inline_rows":[],"errors":[],"inline_replace":True,
        "snapshot_mode":"manual_verified_snapshot"
    }
    try:
        snap=json.loads(KDHC_SNAPSHOT.read_text(encoding="utf-8"))
    except Exception as e:
        out["errors"].append(f"snapshot: {type(e).__name__}: {e}")
        out["parseable_attachments"]=0;out["status"]="FETCH_FAILED";return out
    keep={year-1,year}
    official=(snap.get("provenance") or {}).get("official_listing_url") or (src.get("listing_urls") or [""])[0]
    for ri,r in enumerate(snap.get("rows") or [],start=1):
        date=str(r.get("date") or "")
        try:y=int(date[:4])
        except Exception:continue
        if y not in keep:continue
        out["inline_rows"].append({
            "source_key":src["key"],"institution":src["institution"],
            "cohort":src.get("cohort","public_enterprise_leadership"),
            "role":str(r.get("role") or "경영진"),"department":"",
            "used_date":date,"used_time":"","merchant":str(r.get("merchant") or ""),"address":"",
            "purpose":str(r.get("purpose") or ""),"people":r.get("people"),"amount":r.get("amount"),
            "source_amount_scale":1,"payment_method":"","source_category":"경영진 업무추진비",
            "source_url":official,"source_sheet":"verified_snapshot","source_row":ri,
            "evidence_url":str(r.get("evidence_url") or ""),"evidence_type":str(r.get("evidence_type") or ""),
            "confidence":str(r.get("confidence") or "")
        })
    out["parseable_attachments"]=1 if out["inline_rows"] else 0
    out["status"]="PARSEABLE_FOUND" if out["inline_rows"] else "NO_FILES_FOUND"
    return out

def discover_source(src,year,detail_limit):
    if src.get("key")=="kepco" and src.get("verified") and src.get("publish"):
        return discover_kepco(src,year)
    if src.get("key")=="kogas" and src.get("verified") and src.get("publish"):
        return discover_kogas(src,year,detail_limit)
    if src.get("key")=="kwater" and src.get("verified") and src.get("publish"):
        return discover_kwater(src,year)
    if src.get("key")=="kdhc" and src.get("verified") and src.get("publish"):
        return discover_kdhc(src,year)
    if src.get("key")=="kospo" and src.get("verified") and src.get("publish"):
        return discover_kospo(src,year)
    if src.get("key")=="komipo" and src.get("verified") and src.get("publish"):
        return discover_komipo(src,year,detail_limit)
    if src.get("key")=="hf" and src.get("verified") and src.get("publish"):
        return discover_hf(year)
    if src.get("key")=="hug" and src.get("verified") and src.get("publish"):
        return discover_hug(year)
    if src.get("key")=="ksure" and src.get("verified") and src.get("publish"):
        return discover_ksure(year)
    if src.get("key")=="nps" and src.get("verified") and src.get("publish"):
        return discover_nps(year)
    lookback=max(0,int(src.get("lookback_years",1)))
    years={year-i for i in range(lookback+1)}
    out={"key":src["key"],"institution":src["institution"],"cohort":src.get("cohort","public_enterprise_leadership"),"default_role":src.get("default_role","기관장"),"years":sorted(years),"pages":[],"attachments":[],"errors":[]}
    if not src.get("verified") or not src.get("publish"):
        out["status"]="TRACK_ONLY";return out
    seen_att=set();seen_page=set()
    listings=listing_urls(src)
    listing_docs=[]
    if listings:
        with ThreadPoolExecutor(max_workers=min(8,len(listings))) as pool:
            future_map={pool.submit(fetch,listing):listing for listing in listings}
            for fut in as_completed(future_map):
                listing=future_map[fut]
                try:doc=fut.result()
                except Exception as e:
                    out["errors"].append(f"listing {listing}: {type(e).__name__}: {e}");continue
                out["pages"].append(listing);listing_docs.append((listing,doc))
    detail_jobs=[]
    for listing,doc in listing_docs:
        links=parse_links(listing,doc)
        details=[x for x in links if not looks_file(x) and relevant_detail(x,years)][:detail_limit]
        direct=[x for x in links if looks_file(x) and relevant_detail(x,years)]
        for x in direct:
            if x["url"] in seen_att:continue
            seen_att.add(x["url"]);y,m=extract_year_month(x["text"]);out["attachments"].append({**x,"year":y,"month":m,"parent":listing})
        for x in details:
            if x["url"] in seen_page:continue
            seen_page.add(x["url"]);detail_jobs.append(x)
    if detail_jobs:
        with ThreadPoolExecutor(max_workers=min(8,len(detail_jobs))) as pool:
            future_map={pool.submit(fetch,x["url"]):x for x in detail_jobs}
            for fut in as_completed(future_map):
                x=future_map[fut]
                try:ddoc=fut.result()
                except Exception as e:
                    out["errors"].append(f"detail {x['url']}: {type(e).__name__}: {e}");continue
                for a in parse_links(x["url"],ddoc):
                    if not looks_file(a):continue
                    label=(x.get("text","")+" "+a.get("text","")).strip()
                    if not relevant_detail({"text":label,"url":a["url"]},years):continue
                    if a["url"] in seen_att:continue
                    seen_att.add(a["url"]);y,m=extract_year_month(label);out["attachments"].append({"text":label,"url":a["url"],"year":y,"month":m,"parent":x["url"]})
    parseable=sum(any(ext in (a.get("text","")+" "+a.get("url","")).lower() for ext in FILE_EXTS) for a in out["attachments"])
    out["parseable_attachments"]=parseable
    out["status"]="PARSEABLE_FOUND" if parseable else ("FETCH_FAILED" if out["errors"] else "NO_FILES_FOUND")
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--year",type=int,default=datetime.now().year);ap.add_argument("--incremental",action="store_true");ap.add_argument("--detail-limit",type=int,default=18);args=ap.parse_args()
    reg=json.loads(REGISTRY.read_text(encoding="utf-8"));sources=reg.get("sources",[])
    previous={};path=REPORTS/"public-enterprise-discovery.json"
    if args.incremental and path.exists():
        try:previous={x.get("key"):x for x in json.loads(path.read_text(encoding="utf-8")).get("sources",[])}
        except Exception:previous={}
    rows=[]
    for src in sources:
        fresh=discover_source(src,args.year,args.detail_limit)
        old=previous.get(src.get("key")) or {}
        if args.incremental and old and fresh.get("status")!="TRACK_ONLY":
            amap={str(a.get("url") or ""):a for a in old.get("attachments",[]) if a.get("url")}
            for a in fresh.get("attachments",[]):
                if a.get("url"):amap[str(a["url"])]=a
            fresh["attachments"]=list(amap.values())
            fresh["pages"]=list(dict.fromkeys((old.get("pages") or [])+(fresh.get("pages") or [])))
            if not fresh.get("inline_replace"):
                old_inline={str(x.get("row_id") or x.get("source_url","")+":"+str(x.get("source_row",""))):x for x in old.get("inline_rows",[])}
                for x in fresh.get("inline_rows",[]):
                    old_inline[str(x.get("row_id") or x.get("source_url","")+":"+str(x.get("source_row","")))]=x
                fresh["inline_rows"]=list(old_inline.values())
            fresh["parseable_attachments"]=sum(any(ext in (a.get("text","")+" "+a.get("url","")).lower() for ext in FILE_EXTS) for a in fresh["attachments"])
            if fresh.get("inline_rows"):fresh["parseable_attachments"]=max(fresh["parseable_attachments"],len(fresh.get("pages") or [1]))
            if fresh["parseable_attachments"]:fresh["status"]="PARSEABLE_FOUND"
            elif old.get("status"):fresh["status"]="STALE_OK:"+str(old["status"])
        rows.append(fresh)
    REPORTS.mkdir(exist_ok=True)
    payload={"generated_at":datetime.now().isoformat(timespec="seconds"),"year":args.year,"refresh_mode":"incremental" if args.incremental else "full","sources":rows}
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"sources":len(rows),"parseable_sources":sum(x.get("parseable_attachments",0)>0 for x in rows),"files":sum(len(x.get("attachments",[])) for x in rows),"statuses":{x["key"]:x["status"] for x in rows}},ensure_ascii=False))

if __name__=="__main__":main()
