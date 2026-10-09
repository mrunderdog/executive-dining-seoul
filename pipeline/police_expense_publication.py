"""Strict guard for publishing official Police Agency *expense-user* venues.

This is not a visit dataset. A disclosed expense user/manager is not proven
to be physically present, even if merchant and store address are corroborated.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from venue_eligibility import is_non_venue_merchant

ROOT=Path(__file__).resolve().parents[1]
STAGING=ROOT/"data/raw/police_expense_staging.json"
MANIFEST=ROOT/"sources/police_verified_expense_venues.json"
TRUSTED={"www.police.go.kr","police.go.kr"}

def clean(value):
    return " ".join(str(value or "").split())

def select_expense_venues(staging:dict,manifest:dict)->list[dict]:
    if staging.get("publication_enabled") is not False:
        raise ValueError("source records must remain STAGING_ONLY")
    if manifest.get("schema_version")!=1:
        raise ValueError("Unknown police expense venue manifest schema")
    policy={}
    for v in manifest.get("venues",[]):
        key=clean(v.get("merchant"))
        if key in policy:
            raise ValueError("Duplicate verified merchant policy")
        if (v.get("source_key")!="national_police"
            or not key or is_non_venue_merchant(key)
            or not clean(v.get("address")) or not clean(v.get("approved_role"))
            or len(set(v.get("address_evidence_urls") or []))<2
            or not clean(v.get("source_pdf_sha256"))
            or v.get("attendance_confirmed") is not False):
            raise ValueError("Invalid, ambiguous or attendee-claiming Police venue policy: "+key)
        url=v.get("official_pdf_url") or ""
        p=urlsplit(url)
        if p.scheme!="https" or p.hostname not in TRUSTED or p.path!="/component/file/ND_fileDownload.do":
            raise ValueError("Untrusted Police official PDF URL")
        policy[key]=v
    matched=defaultdict(list)
    for row in staging.get("transactions",[]):
        name=clean(row.get("merchant"))
        v=policy.get(name)
        if not v:continue
        if (row.get("source_key")!="national_police" or row.get("institution")!="경찰청"
            or clean(row.get("role"))!=clean(v["approved_role"])
            or row.get("pdf_sha256")!=v["source_pdf_sha256"]
            or row.get("source_url")!=v["official_pdf_url"]
            or row.get("actor_evidence")!="EXPLICIT_PDF_USER_COLUMN"
            or row.get("attendance_evidence")!="NOT_ESTABLISHED"
            or row.get("publication_status")!="STAGING_ONLY"
            or not clean(row.get("row_id"))):
            continue
        detail=urlsplit(row.get("source_detail_url") or "")
        if detail.scheme!="https" or detail.hostname not in TRUSTED:
            continue
        try:
            d=date.fromisoformat(clean(row.get("used_date")))
            amt=int(row.get("amount"))
        except (TypeError,ValueError):
            continue
        if not (2000<=d.year<=date.today().year and amt>0):continue
        matched[name].append(row)
    result=[]
    for merchant,rows in sorted(matched.items()):
        v=policy[merchant]
        unique={r["row_id"]:r for r in rows}
        tx=sorted(unique.values(),key=lambda r:(r["used_date"],r["row_id"]),reverse=True)
        dates=sorted({r["used_date"] for r in tx})
        if not tx:continue
        spend=sum(r["amount"] for r in tx)
        result.append({
            "name":merchant,"origin":"경찰청(집행 명의)","region":"서울",
            "jurisdiction":"대한민국","institution":"경찰청","institutions":["경찰청"],
            "type":"executive","destination":None,
            "published_source":"police_expense_user_only","cohort":"police_leadership",
            "source_verified_expense_only":True,
            "attendance_status":"NOT_ESTABLISHED",
            "executive":{"rank":len(result)+1,"score":0,"exec_events":0,
              "spending_events":len(tx),"roles":1,"months":len({d[:7] for d in dates}),
              "evening_ratio":0,"source":"police_expense_user_only",
              "top_official_visits":0,"top_role_tier":"police_bureau_head",
              "top_role_label":clean(v["approved_role"])+" (집행 명의)"},
            "address":clean(v["address"]),"search_query":merchant+" "+clean(v["address"]),
            "business":{"display":clean(v.get("display")) or merchant,
              "category":clean(v.get("category")) or "음식점","phone":clean(v.get("phone")),
              "status":"업소 위치 독립 검증·경찰청 업무추진비 원문 교차검증",
              "note":"경찰청 고위직 명의의 공식 업무추진비 집행처입니다. 해당 인물의 실제 참석·방문을 확인한 기록이 아닙니다.",
              "rating":"","url":v["address_evidence_urls"][0],"verification_confidence":"HIGH"},
            "evidence":{"visits":0,"spending_events":len(tx),"spend":spend,"people":0,
              "months":len({d[:7] for d in dates}),"evening":0,"evening_ratio":0,"ppc":0,
              "date_min":dates[0],"date_max":dates[-1],
              "roles":[{"role":clean(v["approved_role"])+" (집행 명의)","visits":0,
                "spending_events":len(tx),"people":0,"spend":spend}],
              "purposes":[],"recent":[{
                  "date":r["used_date"],"role":"경찰청 "+clean(r["role"])+" (집행 명의)",
                  "people":0,"amount":r["amount"],"purpose":clean(r.get("purpose")),
                  "source":r["source_url"],"attendance_status":"NOT_ESTABLISHED",
                  "expense_user_only":True} for r in tx[:12]],
              "source_rows":[r["row_id"] for r in tx]},
            "why":f"경찰청 {clean(v['approved_role'])} 명의 공식 업무추진비 {len(tx)}건·{spend:,}원. 거래처와 식당 주소는 확인됐으나 명의자의 실제 식사 참석 여부는 확인되지 않았습니다.",
        })
    return result

def load_police_expense_records()->list[dict]:
    if not STAGING.exists() or not MANIFEST.exists():return []
    data=json.loads(STAGING.read_text(encoding="utf-8"))
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    return select_expense_venues(data,manifest)
