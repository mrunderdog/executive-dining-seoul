#!/usr/bin/env python3
"""Rank LOCALDATA expansion by published evidence, never by guessed locality."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COVERAGE=ROOT/"reports/localdata-regional-coverage.json"
OUTPUT=ROOT/"reports/localdata-expansion-priority.json"
CURRENT={"서울서대문구","서울중구","서울종로구","서울서초구",
         "서울영등포구","경기광명시","경기고양시","경기안양시"}

def build(report):
    rows=[]
    for entry in report["regions"]:
        total=int(entry["venues"])
        usable=int(entry["with_road_building"])
        missing=int(entry["missing_road_building"])
        if usable+missing != total:
            raise ValueError("Inconsistent region coverage: "+entry["region"])
        # Eligible means a comparable location exists, NOT restaurant-license verification.
        rows.append({
            "region":entry["region"],
            "orgCode":entry["orgCode"],
            "published_venue_count":total,
            "address_ready_count":usable,
            "address_remediation_count":missing,
            "institution_count":int(entry["institution_origin_count"]),
            "top_institution_origins":entry.get("top_origins",[]),
            "currently_scheduled":entry["region"] in CURRENT,
            "next_action":"MONTHLY_AUDIT" if entry["region"] in CURRENT else
                          ("VERIFY_OFFICIAL_CSV_AND_JURISDICTION" if usable else "FIX_SOURCE_ADDRESSES"),
            "official_license_verified":False,
            "payment_branch_verified":False,
            "individual_attendance_verified":False
        })
    rows.sort(key=lambda r:(r["currently_scheduled"],-r["address_ready_count"],
                            -r["institution_count"],r["region"]))
    return {
        "source":"reports/localdata-regional-coverage.json",
        "scoring_policy":"Prioritize unscheduled regions by address-ready published venues, then institution breadth. No implied official CSV match.",
        "scope_policy":"Download official CSV only after jurisdiction code and >=80% address jurisdiction confirmation; <=15 jurisdictions per audit batch.",
        "total_published_venues":report["total_published_venues"],
        "unrouted_venues":report["unrouted_venues"],
        "national_unrouted_reason_counts":report.get("unrouted_reason_counts",{}),
        "current_monthly_jurisdictions":sorted(CURRENT),
        "candidate_jurisdictions":rows,
        "next_candidate_regions":[r["region"] for r in rows if not r["currently_scheduled"] and r["address_ready_count"]>0][:7],
        "verification_semantics":"License registration != card merchant identity != actual attendee."
    }

def main():
    report=json.loads(COVERAGE.read_text(encoding="utf-8"))
    result=build(report)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    assert sum(r["published_venue_count"] for r in result["candidate_jurisdictions"])==report["routed_venues"]
    assert sum(r["address_ready_count"] for r in result["candidate_jurisdictions"])==report["road_building_verifiable"]
    print(json.dumps({"published":result["total_published_venues"],
        "unrouted":result["unrouted_venues"],"next_candidates":result["next_candidate_regions"]},ensure_ascii=False))
if __name__=="__main__":main()
