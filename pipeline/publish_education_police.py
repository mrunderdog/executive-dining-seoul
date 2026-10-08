#!/usr/bin/env python3
"""Publish only address-verified venue matches from vetted senior-official rows.

Input staging is generated from official documents during CI. A restaurant
listing is NOT evidence of official attendance; the source attendee field must
identify the official explicitly. Unknown venue labels stay in the audit queue.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from leadership_scope import actor_explicit_in_target, valid_transaction
from venue_eligibility import is_non_venue_merchant

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data/raw/education_police_expense_staging.json"
MANIFEST=ROOT/"sources/education_police_verified_venues.json"
REGISTRY=ROOT/"sources/education_police_registry.json"
OUTPUT=ROOT/"reports/education-police-approved-venues.json"

def clean(s):
    return " ".join(str(s or "").split())

def select(rows, manifest, registry):
    sources={x["key"]:x for x in registry.get("sources",[])}
    verified={(x["source_key"], clean(x["merchant"])):x for x in manifest.get("venues",[])}
    grouped=defaultdict(list)
    skipped={}
    for r in rows:
        key=(r.get("source_key"),clean(r.get("merchant")))
        v=verified.get(key)
        reason=""
        source=sources.get(r.get("source_key"))
        if not v or not source:reason="UNVERIFIED_VENUE"
        elif not v.get("address") or v.get("verification_confidence")!="HIGH" or len(v.get("sources") or [])<2:reason="ADDRESS_NOT_CORROBORATED"
        elif is_non_venue_merchant(r.get("merchant")):reason="NON_VENUE"
        elif clean(r.get("role")) not in v.get("allowed_roles",[]):reason="ROLE_NOT_APPROVED"
        elif not actor_explicit_in_target(r.get("role"),r.get("target")):reason="ACTOR_NOT_EXPLICIT"
        elif not valid_transaction(r,set(source["official_hosts"])):reason="INVALID_TRANSACTION"
        elif urlsplit(r.get("source_detail_url") or "").hostname not in source["official_hosts"]:reason="NO_OFFICIAL_DETAIL"
        elif not r.get("row_id") or r.get("publication_status")!="STAGING_ONLY":reason="NO_STAGING_LINEAGE"
        if reason:
            skipped[reason]=skipped.get(reason,0)+1
            continue
        grouped[key].append(r)
    out=[]
    for key,selected in sorted(grouped.items()):
        v=verified[key]
        # Avoid replaying one transaction more than once.
        unique={r["row_id"]:r for r in selected}
        items=sorted(unique.values(),key=lambda x:(x["used_date"],x["row_id"]),reverse=True)
        out.append({
            "source_key":key[0],"institution":sources[key[0]]["institution"],
            "merchant":v["merchant"],"address":v["address"],"category":v["category"],
            "phone":v.get("phone",""),"verification_confidence":"HIGH",
            "address_evidence_urls":v["sources"],"transactions":[
                {"row_id":r["row_id"],"date":r["used_date"],"amount":r["amount"],
                 "role":r["role"],"purpose":r.get("purpose",""),
                 "target":r.get("target",""),"source_url":r["source_url"],
                 "source_detail_url":r["source_detail_url"]}
                for r in items
            ],
        })
    return {"publication_enabled":True,"generated_at":datetime.now(timezone.utc).isoformat(),
            "approved_venues":len(out),
            "approved_transactions":sum(len(x["transactions"]) for x in out),
            "unpublished_counts":skipped,"venues":out}

def main():
    staging=json.loads(RAW.read_text(encoding="utf-8"))
    assert staging.get("publication_enabled") is False
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    registry=json.loads(REGISTRY.read_text(encoding="utf-8"))
    result=select(staging.get("rows") or [],manifest,registry)
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"venues":result["approved_venues"],"transactions":result["approved_transactions"],
                      "blocked":result["unpublished_counts"]},ensure_ascii=False))
    if not result["approved_venues"]:raise SystemExit("No approved venues; retain last-good dataset")

if __name__=="__main__":
    main()
