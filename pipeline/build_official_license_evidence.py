#!/usr/bin/env python3
"""Report official registration evidence without claiming payment-branch identity."""
import argparse
import json
from collections import Counter
from pathlib import Path

def report(audit):
    official_sources=audit.get("sources") or []
    sourced=bool(official_sources) and all(
        s.get("sha256") and s.get("jurisdiction_confirmed_rows",0)>0
        and s.get("routable_rows",0)>0
        and s["jurisdiction_confirmed_rows"]/s["routable_rows"]>=0.8
        for s in official_sources
    )
    rows=[]
    for v in audit.get("venues") or []:
        status=v.get("license_match_status")
        legal_match=status in {"EXACT_NAME_AND_ADDRESS","NAME_AND_BUILDING_ADDRESS_FLOOR_UNVERIFIED"}
        legal_match=bool(sourced and legal_match and v.get("license_name") and v.get("license_address"))
        evidence_state=("OFFICIAL_LICENSE_EXACT_ADDRESS" if status=="EXACT_NAME_AND_ADDRESS"
                       else "OFFICIAL_LICENSE_SAME_BUILDING_UNIT_UNVERIFIED" if legal_match
                       else "OFFICIAL_LICENSE_IDENTITY_NOT_CONFIRMED")
        if not legal_match:
            evidence_state="OFFICIAL_LICENSE_IDENTITY_NOT_CONFIRMED"
        rows.append({
            "entity_id":v.get("entity_id"),"merchant":v.get("merchant"),
            "original_address":v.get("address"),"region":v.get("region"),
            "license_evidence_state":evidence_state,
            "official_licensed_name":v.get("license_name") if legal_match else None,
            "official_licensed_address":v.get("license_address") if legal_match else None,
            "official_license_status":v.get("license_business_status") if legal_match else None,
            "official_license_permit_date":v.get("license_permit_date") if legal_match else None,
            "license_matches_original_merchant_name":legal_match,
            "unit_or_floor_verified":bool(legal_match and status=="EXACT_NAME_AND_ADDRESS"),
            "payment_branch_verified":False,
            "individual_attendance_verified":False,
        })
    return {
        "checked_at_utc":audit.get("checked_at_utc"),
        "geographic_scope":audit.get("geographic_scope"),
        "official_source_provenance":official_sources,
        "official_sources_validated":sourced,
        "total_venues":len(rows),
        "state_counts":dict(Counter(r["license_evidence_state"] for r in rows)),
        "policy":"The official licence corroborates a business name/address only; never a card merchant branch, spend transaction, personal presence, current operation or licence ownership.",
        "venues":rows,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    d=report(json.loads(Path(a.audit).read_text(encoding="utf-8")))
    path=Path(a.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"count":d["total_venues"],"states":d["state_counts"]},ensure_ascii=False))

if __name__=="__main__":
    main()
