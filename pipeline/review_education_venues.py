#!/usr/bin/env python3
"""Deterministic review queue from OFFICIAL staged education / police transactions.

Only role-explicit payments are reviewable as individual senior-official dining.
No address may be guessed from a bare merchant label; publication is separate.
"""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
from leadership_scope import actor_explicit_in_target, valid_transaction
from venue_eligibility import is_non_venue_merchant, normalized_merchant

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data/raw/education_police_expense_staging.json"
REG=ROOT/"sources/education_police_registry.json"
OUT_JSON=ROOT/"reports/education-police-venue-review.json"
OUT_MD=ROOT/"reports/education-police-venue-review.md"

def review(rows:list[dict],sources:list[dict])->dict:
    scope={x["key"]:x for x in sources}
    eligible=defaultdict(list)
    excluded=defaultdict(int)
    for r in rows:
        src=scope.get(r.get("source_key"))
        if not src or not valid_transaction(r,set(src.get("official_hosts") or [])):
            excluded["INVALID_OFFICIAL_LINEAGE"]+=1
            continue
        if not actor_explicit_in_target(r.get("role"),r.get("target")):
            excluded["OFFICIAL_PRESENCE_UNCONFIRMED"]+=1
            continue
        if is_non_venue_merchant(r.get("merchant")):
            excluded["GENERIC_BILLER_OR_NON_VENUE"]+=1
            continue
        key=(r["source_key"],normalized_merchant(r.get("merchant")))
        eligible[key].append(r)
    candidates=[]
    for (key,_),group in eligible.items():
        group.sort(key=lambda r:(r.get("used_date") or "",r.get("row_id") or ""))
        # Never deduplicate by amount/date: real repeat transactions can occur.
        unique={r["row_id"]:r for r in group if r.get("row_id")}
        events=list(unique.values())
        if not events:
            excluded["MISSING_TRANSACTION_ID"]+=len(group)
            continue
        candidates.append({
            "source_key":key,
            "institution":scope[key]["institution"],
            "merchant":events[0]["merchant"],
            "roles":sorted({r["role"] for r in events}),
            "transactions":len(events),
            "spend":sum(int(r["amount"]) for r in events),
            "dates":sorted({r["used_date"] for r in events}),
            "source_urls":sorted({r["source_url"] for r in events}),
            "source_detail_urls":sorted({r["source_detail_url"] for r in events}),
            "address_verified":False,
            "venue_identity_status":"MANUAL_VERIFICATION_REQUIRED",
            "map_status":"NOT_PUBLISHED",
        })
    candidates.sort(key=lambda c:(-c["transactions"],-c["spend"],c["merchant"]))
    return {
      "staged_rows":len(rows),"reviewable_transactions":sum(c["transactions"] for c in candidates),
      "candidates":candidates,"excluded":dict(excluded),
      "publication_enabled":False,
      "note":"A merchant label in an expense disclosure does not by itself establish restaurant identity or a verified address."
    }

def main():
    staged=json.loads(RAW.read_text(encoding="utf-8"))
    assert staged.get("publication_enabled") is False
    registry=json.loads(REG.read_text(encoding="utf-8"))
    result=review(staged.get("rows") or [],registry.get("sources") or [])
    OUT_JSON.parent.mkdir(parents=True,exist_ok=True)
    OUT_JSON.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# Education / police venue identity review","",
           "Staged transactions are not published unless official attendance and address/venue identity are independently verified.","",
           f"- Source transactions: {result['staged_rows']}",
           f"- Explicitly attributable, non-biller transactions: {result['reviewable_transactions']}",
           f"- Venue-label review candidates: {len(result['candidates'])}","",
           "| Institution | Merchant label | Transactions | Amount (KRW) | Role |",
           "|---|---|---:|---:|---|"]
    for c in result["candidates"]:
        lines.append(f"| {c['institution']} | {c['merchant'].replace('|','/')} | {c['transactions']} | {c['spend']:,} | {', '.join(c['roles'])} |")
    OUT_MD.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"staged":result["staged_rows"],"reviewable":result["reviewable_transactions"],
                      "candidates":len(result["candidates"]),"excluded":result["excluded"]},ensure_ascii=False))
    # Printed review is limited to identities of publicly disclosed venues and roles,
    # never named individual staff/attendees or unpublished venue inferences.
    for c in result["candidates"][:35]:
        print("VENUE_REVIEW",json.dumps({k:c[k] for k in ("source_key","merchant","roles","transactions","spend","dates")},ensure_ascii=False))

if __name__=="__main__":
    main()
