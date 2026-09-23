#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from ingest_central_executive_expense import fetch, rows_from, normalize, clean

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/"reports"
RAW_DIR=ROOT/"data"/"raw"
DISCOVERY=REPORTS/"justice-leadership-discovery.json"
REGISTRY=ROOT/"sources"/"justice_leadership_registry.json"
SUPPORTED=(".xlsx",".xls",".csv",".hwpx",".pdf")

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


def justice_domain(institution:str,source_key:str)->str:
    if institution in {"법무부","법제처"}: return "legal_administration"
    if "검찰" in institution or source_key.startswith("prosecution_"): return "prosecution"
    if "헌법재판소" in institution: return "constitutional_court"
    if "공직자범죄수사처" in institution: return "cio"
    if "법원" in institution or source_key=="supreme_court": return "judiciary"
    return "justice_other"


def parse_source(src:dict,all_rows:list,files:list,errors:list):
    for a in src.get("attachments",[]):
        label=text(a.get("text")) or a.get("url","")
        url=a.get("url") or ""
        low=(label+" "+url).lower()
        if "synapview" in url.lower() or not any(ext in low for ext in SUPPORTED):
            continue
        try:
            blob=fetch(url)
            info={"institution":src["institution"],"key":src["key"],"url":url,"bytes":len(blob),"sheets":[]}
            role_hint=detailed_role(label,src["institution"],src.get("default_role",""))
            for sheet,rows in rows_from(blob,label):
                norm,si=normalize(rows,sheet,{
                    "key":src["key"],"institution":src["institution"],"url":url,
                    "default_role":role_hint
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
                all_rows.extend(norm); info["sheets"].append(si)
            files.append(info)
        except Exception as e:
            errors.append({"institution":src.get("institution"),"source_key":src.get("key"),"url":url,
                           "error":f"{type(e).__name__}: {e}"})


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--year",type=int,default=datetime.now().year); args=ap.parse_args()
    if not DISCOVERY.exists():
        raise SystemExit("run justice_leadership_discovery.py first")
    d=json.loads(DISCOVERY.read_text(encoding="utf-8"))
    reg=json.loads(REGISTRY.read_text(encoding="utf-8"))
    inherited_cfg={x.get("source_key"):x for x in reg.get("inherited_central_sources",[])}
    all_rows=[]; files=[]; errors=[]

    for src in d.get("inherited_sources",[]):
        cfg=inherited_cfg.get(src.get("key"),{})
        merged={**src,"source_type":cfg.get("source_type","official_routine")}
        parse_source(merged,all_rows,files,errors)
    for src in d.get("sources",[]):
        parse_source(src,all_rows,files,errors)

    unique={r["row_id"]:r for r in all_rows}
    rows=sorted(unique.values(),key=lambda r:(r.get("used_date") or "",r.get("institution") or "",r["row_id"]))
    RAW_DIR.mkdir(exist_ok=True)
    payload={"schema_version":1,"generated_at":datetime.now().isoformat(timespec="seconds"),
             "cohort":"justice_leadership","row_count":len(rows),"rows":rows,"files":files,"errors":errors}
    (RAW_DIR/"justice_leadership_expense.json").write_text(
        json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8"
    )
    by_inst=Counter(r.get("institution") or "(unknown)" for r in rows)
    by_domain=Counter(r.get("justice_domain") or "(unknown)" for r in rows)
    merchant_rows=sum(bool(text(r.get("merchant"))) for r in rows)
    report=["# Justice leadership expense ingestion","",f"- Rows: **{len(rows)}**",
            f"- Merchant rows: **{merchant_rows}**",f"- Files: **{len(files)}**",f"- Errors: **{len(errors)}**",
            "","## Rows by institution",""]
    for k,v in by_inst.most_common(): report.append(f"- {k}: {v}")
    report+=["","## Rows by domain",""]
    for k,v in by_domain.most_common(): report.append(f"- {k}: {v}")
    if errors:
        report+=["","## Errors",""]
        for e in errors[:80]: report.append(f"- {e['institution']} / {e['source_key']}: {e['error']} — {e['url']}")
    (REPORTS/"justice-leadership-ingestion.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    print(json.dumps({"rows":len(rows),"merchant_rows":merchant_rows,"files":len(files),"errors":len(errors),
                      "institutions":dict(by_inst)},ensure_ascii=False))


if __name__=="__main__": main()
