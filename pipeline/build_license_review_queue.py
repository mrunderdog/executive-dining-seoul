#!/usr/bin/env python3
"""Review-only grouping of official licensing mismatches, never proof of payment."""
import argparse
import json
from collections import Counter
from pathlib import Path

def classify(venue):
    address=str(venue.get("address") or "")
    if "-0@" in address:
        return "ADDRESS_FORMAT_REVIEW"
    if int(venue.get("official_building_business_count") or 0)>0:
        return "SAME_BUILDING_NAME_REVIEW"
    return "NO_SAME_BUILDING_CANDIDATE"

def build(audit):
    rows=[]
    for venue in audit.get("venues") or []:
        if venue.get("license_match_status")!="NOT_MATCHED":
            continue
        neighbors=(venue.get("official_building_businesses") or [])[:5]
        rows.append({
            "region":venue.get("region"),"merchant":venue.get("merchant"),
            "address":venue.get("address"),"entity_id":venue.get("entity_id"),
            "review_reason":classify(venue),
            "official_candidates":[{
                "name":candidate.get("license_name"),
                "address":candidate.get("license_address"),
                "status":candidate.get("license_business_status")
            } for candidate in neighbors],
            "legal_merchant_identity":"NOT_VERIFIED",
            "payment_branch_identity":"NOT_VERIFIED",
            "personal_attendance":"NOT_ESTABLISHED"
        })
    return {
        "audit_scope":audit.get("geographic_scope") or [],
        "total_audited":audit.get("total_venues",0),
        "unmatched_count":len(rows),
        "review_reason_counts":dict(Counter(row["review_reason"] for row in rows)),
        "source_provenance":audit.get("sources") or [],
        "policy":"Candidates only. Same building or similar name does not establish payment branch, merchant or person attendance.",
        "review_queue":rows
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--audit",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    report=build(json.loads(Path(args.audit).read_text(encoding="utf-8")))
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"unmatched":report["unmatched_count"],"reasons":report["review_reason_counts"]},ensure_ascii=False))

if __name__=="__main__":
    main()
