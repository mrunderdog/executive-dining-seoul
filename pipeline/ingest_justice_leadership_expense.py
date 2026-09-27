#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import http.cookiejar
import urllib.request
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from ingest_central_executive_expense import fetch, rows_from, normalize, clean

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/"reports"
RAW_DIR=ROOT/"data"/"raw"
DISCOVERY=REPORTS/"justice-leadership-discovery.json"
REGISTRY=ROOT/"sources"/"justice_leadership_registry.json"
SUPPORTED=(".xlsx",".xls",".csv",".hwp",".hwpx",".pdf")

ROLE_PATTERNS=[
    ("헌법재판소사무처장","헌법재판소사무처장"),
    ("헌법재판소장","헌법재판소장"),
    ("고위공직자범죄수사처장","고위공직자범죄수사처장"),
    ("검찰총장","검찰총장"),
    ("서울중앙지방검찰청 검사장","서울중앙지방검찰청 검사장"),
    ("서울동부지방검찰청 검사장","서울동부지방검찰청 검사장"),
    ("서울북부지방검찰청 검사장","서울북부지방검찰청 검사장"),
    ("수원지방검찰청 검사장","수원지방검찰청 검사장"),
    ("인천지방검찰청 검사장","인천지방검찰청 검사장"),
    ("출입국·외국인정책본부장","출입국·외국인정책본부장"),
    ("출입국외국인정책본부장","출입국·외국인정책본부장"),
    ("범죄예방정책국장","범죄예방정책국장"),
    ("국제법무국장","국제법무국장"),
    ("검찰국장","검찰국장"),
    ("법무실장","법무실장"),
    ("교정본부장","교정본부장"),
    ("기획조정실장","기획조정실장"),
    ("감찰관","감찰관"),
    ("법제처장","법제처장"),
    ("법제처차장","법제처차장"),
    ("법제정책국장","법제정책국장"),
    ("법령정비국장","법령정비국장"),
    ("법령해석국장","법령해석국장"),
    ("법제정보지원국장","법제정보지원국장"),
    ("법제조정정책관","법제조정정책관"),
    ("법제자문조정관","법제자문조정관"),
    ("기획조정관","기획조정관"),
    ("사회문화법제국","사회문화법제국"),
    ("행정법제국장","행정법제국장"),
    ("경제법제국장","경제법제국장"),
    ("차관","법무부 차관"),
    ("장관","법무부 장관"),
]
GENERIC_ROLES={"","국장","실장","처장","차장","차관","장관","본부장","감찰관","직위 미상"}


def text(v): return " ".join(str(v or "").split()).strip()


def detailed_role(label:str,institution:str,default_role:str="")->str:
    s=text(label)
    for needle,role in ROLE_PATTERNS:
        if needle in s:
            if needle=="차관" and institution!="법무부": continue
            if needle=="장관" and institution!="법무부": continue
            return role
    return text(default_role)


def fetch_attachment(url:str,parent_url:str=""):
    if "moj.go.kr/" not in url:
        return fetch(url)
    # MOJ download.do requires a fresh session cookie. The server also closes
    # some downloads transiently, so retry with a new session each time.
    last=None
    for attempt in range(2):
        try:
            jar=http.cookiejar.CookieJar()
            opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            headers={"User-Agent":"ExecutiveDiningSeoul/2.1 (+https://github.com/mrunderdog/executive-dining-seoul)","Accept":"*/*"}
            if parent_url:
                with opener.open(urllib.request.Request(parent_url,headers=headers),timeout=15) as r:
                    r.read(256)
                headers["Referer"]=parent_url
            with opener.open(urllib.request.Request(url,headers=headers),timeout=30) as r:
                return r.read()
        except Exception as e:
            last=e
            if attempt < 1:
                time.sleep(1.0)
    raise last


def justice_domain(institution:str,source_key:str)->str:
    if institution in {"법무부","법제처"}: return "legal_administration"
    if "검찰" in institution or source_key.startswith("prosecution_"): return "prosecution"
    if "헌법재판소" in institution: return "constitutional_court"
    if "공직자범죄수사처" in institution: return "cio"
    if "법원" in institution or source_key=="supreme_court": return "judiciary"
    return "justice_other"


def parse_attachment(src:dict,a:dict):
    label=text(a.get("text")) or a.get("url","")
    url=a.get("url") or ""
    low=(label+" "+url).lower()
    if "synapview" in url.lower() or not any(ext in low for ext in SUPPORTED):
        return [],None,None
    try:
        blob=fetch_attachment(url,a.get("parent",""))
        info={"institution":src["institution"],"key":src["key"],"url":url,"bytes":len(blob),"sheets":[]}
        role_hint=detailed_role(label,src["institution"],src.get("default_role",""))
        parsed=[]
        parsed_sheets=list(rows_from(blob,label))
        if src.get("key")=="ministry_justice" and ".pdf" in label.lower() and len(parsed_sheets)>1:
            combined=[]
            for _,page_rows in parsed_sheets:
                combined.extend(page_rows)
            parsed_sheets=[("pdf-combined",combined)]
        for sheet,rows in parsed_sheets:
            norm,si=normalize(rows,sheet,{
                "key":src["key"],"institution":src["institution"],"url":url,
                "default_role":role_hint,"source_year":a.get("year")
            })
            for row in norm:
                role=text(row.get("role"))
                if role in GENERIC_ROLES and role_hint:
                    row["role"]=role_hint
                row["cohort"]="justice_leadership"
                row["justice_domain"]=justice_domain(src["institution"],src["key"])
                row["source_type"]=src.get("source_type","official_routine")
                row["payer_role"]=row.get("role") or role_hint
                row["payer_person"]=""
                row["payer_attribution_confidence"]="role_only"
                row["source_parent_url"]=a.get("parent","")
                row["source_attachment_label"]=label
                row["row_id"]=hashlib.sha256(
                    "|".join(str(row.get(k,"")) for k in (
                        "source_key","payer_role","used_date","merchant","amount","source_url","source_sheet","source_row"
                    )).encode()
                ).hexdigest()[:20]
            parsed.extend(norm); info["sheets"].append(si)
        return parsed,info,None
    except Exception as e:
        return [],None,{
            "institution":src.get("institution"),"source_key":src.get("key"),"url":url,
            "error":f"{type(e).__name__}: {e}"
        }


def parse_source(src:dict,all_rows:list,files:list,errors:list):
    if src.get("merchant_expectation") == "aggregate_only_observed":
        files.append({"institution":src.get("institution"),"key":src.get("key"),"status":"AGGREGATE_ONLY_SKIPPED","sheets":[]})
        return
    attachments=list(src.get("attachments",[]))
    if not attachments:
        return
    # Public attachment servers are the slowest part of the refresh. Keep a
    # small bounded pool: enough to avoid serial 40-file downloads without
    # hammering government sites.
    workers=min(4,len(attachments))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(parse_attachment,src,a) for a in attachments]
        for fut in as_completed(futures):
            parsed,info,error=fut.result()
            all_rows.extend(parsed)
            if info: files.append(info)
            if error: errors.append(error)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,default=datetime.now().year)
    ap.add_argument("--incremental",action="store_true",
                    help="Skip previously successful attachment URLs and merge only new/retried data.")
    args=ap.parse_args()
    if not DISCOVERY.exists():
        raise SystemExit("run justice_leadership_discovery.py first")
    d=json.loads(DISCOVERY.read_text(encoding="utf-8"))
    reg=json.loads(REGISTRY.read_text(encoding="utf-8"))
    inherited_cfg={x.get("source_key"):x for x in reg.get("inherited_central_sources",[])}

    RAW_DIR.mkdir(exist_ok=True)
    out=RAW_DIR/"justice_leadership_expense.json"
    stored={}
    if out.exists():
        try: stored=json.loads(out.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError): stored={}
    previous=stored if args.incremental else {}
    previous_rows=list(previous.get("rows",[]))
    previous_files=list(previous.get("files",[]))
    previous_errors=list(previous.get("errors",[]))
    known_urls={str(f.get("url") or "") for f in previous_files if f.get("url")}

    all_rows=[]; files=[]; errors=[]

    def filtered_source(src):
        if not args.incremental:return src
        return {**src,"attachments":[
            a for a in src.get("attachments",[])
            if str(a.get("url") or "") not in known_urls
        ]}

    for src in d.get("inherited_sources",[]):
        cfg=inherited_cfg.get(src.get("key"),{})
        merged={**filtered_source(src),"source_type":cfg.get("source_type","official_routine")}
        parse_source(merged,all_rows,files,errors)
    for src in d.get("sources",[]):
        parse_source(filtered_source(src),all_rows,files,errors)

    # Aggregate-only sources append bookkeeping entries without URLs; they are
    # not "new files" and should not prevent the no-change fast path.
    new_files=[f for f in files if f.get("url")]
    if args.incremental and not new_files and not errors:
        print(json.dumps({"status":"NO_CHANGE","rows":len(previous_rows),"known_files":len(previous_files)},ensure_ascii=False))
        return

    unique={r["row_id"]:r for r in previous_rows+all_rows}
    rows=sorted(unique.values(),key=lambda r:(r.get("used_date") or "",r.get("institution") or "",r["row_id"]))

    success_urls={str(f.get("url") or "") for f in new_files if f.get("url")}
    file_map={str(f.get("url") or ""):f for f in previous_files if f.get("url")}
    for f in new_files:
        file_map[str(f["url"])]=f
    merged_files=list(file_map.values()) if args.incremental else files

    merged_errors=[e for e in previous_errors if str(e.get("url") or "") not in success_urls] if args.incremental else []
    seen={(str(e.get("url") or ""),str(e.get("error") or "")) for e in merged_errors}
    for e in errors:
        key=(str(e.get("url") or ""),str(e.get("error") or ""))
        if key not in seen:
            merged_errors.append(e);seen.add(key)
    merged_errors=merged_errors[-100:] if args.incremental else errors

    payload={"schema_version":1,"generated_at":datetime.now().isoformat(timespec="seconds"),
             "cohort":"justice_leadership","refresh_mode":"incremental" if args.incremental else "full",
             "new_files":len(new_files),"row_count":len(rows),"rows":rows,
             "files":merged_files,"errors":merged_errors}

    if not args.incremental:
        baseline_rows=list(stored.get("rows",[]))
        if not rows:
            print(json.dumps({
                "status":"STALE_OK:EMPTY_FULL","baseline_rows":len(baseline_rows),
                "reason":"fresh full justice output was empty; committed baseline preserved"
            },ensure_ascii=False))
            return
        if baseline_rows and len(rows) < max(50,int(len(baseline_rows)*0.5)):
            print(json.dumps({
                "status":"STALE_OK:DEGRADED_FULL","fresh_rows":len(rows),
                "baseline_rows":len(baseline_rows),
                "reason":"fresh full justice output fell below 50% of baseline"
            },ensure_ascii=False))
            return

    out.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")

    by_inst=Counter(r.get("institution") or "(unknown)" for r in rows)
    by_domain=Counter(r.get("justice_domain") or "(unknown)" for r in rows)
    merchant_rows=sum(bool(text(r.get("merchant"))) for r in rows)
    report=["# Justice leadership expense ingestion","",f"- Rows: **{len(rows)}**",
            f"- Merchant rows: **{merchant_rows}**",f"- Refresh mode: **{payload['refresh_mode']}**",
            f"- New files: **{len(new_files)}**",f"- Files retained: **{len(merged_files)}**",
            f"- Errors: **{len(merged_errors)}**","","## Rows by institution",""]
    for k,v in by_inst.most_common(): report.append(f"- {k}: {v}")
    report+=["","## Rows by domain",""]
    for k,v in by_domain.most_common(): report.append(f"- {k}: {v}")
    if merged_errors:
        report+=["","## Errors",""]
        for e in merged_errors[:80]: report.append(f"- {e['institution']} / {e['source_key']}: {e['error']} — {e['url']}")
    (REPORTS/"justice-leadership-ingestion.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    print(json.dumps({"status":"UPDATED" if new_files else "RETRIED_ERRORS","rows":len(rows),
                      "merchant_rows":merchant_rows,"new_files":len(new_files),"files":len(merged_files),
                      "errors":len(merged_errors),"institutions":dict(by_inst)},ensure_ascii=False))


if __name__=="__main__": main()
