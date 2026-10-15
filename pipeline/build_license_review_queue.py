#!/usr/bin/env python3
"""Generate unverified-name/address review queues from official licensing audit output."""
import argparse,json
from collections import Counter
from pathlib import Path

def classify(v):
    address=str(v.get("address") or "")
    if "-0@" in address:
        return "ADDRESS_FORMAT_REVIEW"
    if int(v.get("official_building_business_count") or 0)>0:
        return "SAME_BUILDING_NAME_REVIEW"
    return "NO_SAME_BUILDING_CANDIDATE"

def build(data):
    rows=[]
    for v in data["venues"]:
        if v["license_match_status"]!="NOT_MATCHED":continue
        rows.append({
            "region":v.get("region"),"merchant":v["merchant"],"address":v["address"],
            "entity_id":v.get("entity_id"),"review_reason":classify(v),
            "official_candidates":[{"name":c["license_name"],"address":c["license_address"],
                "status":c.get("license_business_status")} for c in
                v.get("official_building_businesses",[])[:5]],
            "legal_merchant_identity":"NOT_VERIFIED",
            "payment_branch_identity":"NOT_VERIFIED",
            "personal_attendance":"NOT_ESTABLISHED"
        })
    count=dict(Counter(r["review_reason"] for r in rows))
    return {"audit_scope":data["geographic_scope"],"total_audited":data["total_venues"],
        "unmatched_count":len(rows),"review_reason_counts":count,
        "source_provenance":data["sources"],
        "policy":"Review candidates only. A shared building or similar name is not proof of card merchant or attendee identity.",
        "review_queue":rows}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    report=build(json.loads(Path(a.audit).read_text(encoding="utf-8")))
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"unmatched":report["unmatched_count"],"reasons":report["review_reason_counts"]},ensure_ascii=False))
if __name__=="__main__":main()
