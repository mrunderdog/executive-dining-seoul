#!/usr/bin/env python3
"""Audit staged senior-official payments; keep all unverified venues off the map."""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from leadership_scope import actor_explicit_in_target
from venue_eligibility import is_non_venue_merchant

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data/raw/education_police_expense_staging.json"
JSON_REPORT=ROOT/"reports/education-police-staging-audit.json"
MD_REPORT=ROOT/"reports/education-police-staging-audit.md"
REGISTRY=ROOT/"sources/education_police_registry.json"

def audit(rows:list[dict], sources:list[dict])->dict:
    groups=defaultdict(list)
    summaries=[]
    flags=[]
    for source in sources:
        subset=[r for r in rows if r.get("source_key")==source["key"]]
        roles=Counter(str(r.get("role") or "") for r in subset)
        explicit=0; unknown=0; nonvenue=0
        for r in subset:
            name=str(r.get("merchant") or "").strip()
            yes=actor_explicit_in_target(r.get("role"),r.get("target"))
            if yes:explicit+=1
            else:unknown+=1
            if is_non_venue_merchant(name):
                nonvenue+=1
                flags.append({"source_key":source["key"],"merchant":name,"reason":"NON_VENUE_BILLER","row_id":r.get("row_id")})
                continue
            groups[(source["key"], str(r.get("role") or ""), name)].append(r)
        summaries.append({"key":source["key"],"institution":source["institution"],
                          "rows":len(subset),"roles":dict(roles),
                          "actor_explicit":explicit,"actor_unconfirmed":unknown,
                          "non_venue_billers":nonvenue,"publication_enabled":False})
    candidates=[]
    for (key,role,name),instances in groups.items():
        explicit=[r for r in instances if actor_explicit_in_target(r.get("role"),r.get("target"))]
        candidates.append({
            "source_key":key,"role":role,"merchant":name,
            "transaction_count":len(instances),"actor_explicit_count":len(explicit),
            "spend":sum(int(r.get("amount") or 0) for r in instances),
            "dates":sorted({str(r.get("used_date") or "") for r in instances}),
            "evidence_urls":sorted({r.get("source_url") for r in instances if r.get("source_url")}),
            "venue_verification":"REVIEW_REQUIRED",
            "map_publication":"BLOCKED",
        })
    candidates.sort(key=lambda x:(x["actor_explicit_count"],x["transaction_count"],x["spend"]),reverse=True)
    return {"generated_at":datetime.now(timezone.utc).isoformat(),
            "publication_enabled":False,
            "staged_transactions":len(rows),
            "sources":summaries,
            "non_venue_flags":flags,
            "candidate_count":len(candidates),
            "candidates":candidates,
            "disclaimer":"Staged expenditure is not proof of personal restaurant attendance. Venue identity/address, official presence and cross-source equivalence require separate verification."}

def main():
    if not RAW.exists():
        raise SystemExit("no education-police staging data to audit")
    data=json.loads(RAW.read_text(encoding="utf-8"))
    registry=json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert data.get("publication_enabled") is False
    report=audit(data.get("rows") or [], registry.get("sources") or [])
    JSON_REPORT.parent.mkdir(parents=True,exist_ok=True)
    JSON_REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# Education / police senior-official staging audit","","Publication is **disabled** until venue identity and actor evidence are independently checked.","",
           "| Institution | Transactions | Explicit actor | Unconfirmed | Non-venue billers |",
           "|---|---:|---:|---:|---:|"]
    for s in report["sources"]:
        lines.append(f"| {s['institution']} | {s['rows']} | {s['actor_explicit']} | {s['actor_unconfirmed']} | {s['non_venue_billers']} |")
    lines += ["",f"Candidate venue labels: **{report['candidate_count']}** (all REVIEW_REQUIRED)","","## Review queue",
              "| Role | Merchant | Payments | Explicit actor | Amount |",
              "|---|---|---:|---:|---:|"]
    for r in report["candidates"][:100]:
        lines.append(f"| {r['role']} | {r['merchant'].replace('|','/')} | {r['transaction_count']} | {r['actor_explicit_count']} | {r['spend']:,} |")
    MD_REPORT.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"staged":report["staged_transactions"],"candidates":report["candidate_count"],
        "by_source":[{"key":s["key"],"transactions":s["rows"],"explicit":s["actor_explicit"],
                      "unconfirmed":s["actor_unconfirmed"],"nonvenue":s["non_venue_billers"]} for s in report["sources"]],
        "publication_enabled":False},ensure_ascii=False))

if __name__=="__main__":
    main()
