#!/usr/bin/env python3
"""Compare nine manually reviewed merchant labels against immutable LOCALDATA audit."""
import argparse,json
from pathlib import Path
from collections import Counter
REVIEW_STATES={"MERCHANT_NAME_AT_ADDRESS_CORROBORATED","GOVERNMENT_EXPENSE_LABELS_DIFFER_BY_DATE","GOVERNMENT_EXPENSE_LABELS_INTERLEAVED_SAME_ADDRESS","DIFFERENT_BUSINESS_LICENSE_SCOPE_REVIEW","MULTIPLE_LICENSEES_UNRESOLVED"}
def build(audit,registry):
    sources={s["district"]:s["sha256"] for s in audit.get("sources",[])}
    expected=registry["source_file_sha256_by_region"]
    if not all(sources.get(k)==v for k,v in expected.items()):
        raise ValueError("Official source fingerprints differ; repeat evidence review")
    byid={v["entity_id"]:v for v in audit["venues"] if v.get("entity_id")}
    rows=[]
    for r in registry["entries"]:
        v=byid.get(r["entity_id"])
        if (not v or v["merchant"]!=r["merchant"] or v["address"]!=r["original_address"]
             or v["region"]!=r["region"] or v["license_match_status"]!="NOT_MATCHED"
             or r["assessment"] not in REVIEW_STATES):
            raise ValueError("Unmatched identity or unsupported assessment: "+r["entity_id"])
        official={x["license_name"] for x in v.get("official_building_businesses",[])}
        if not set(r["expected_official_license_names"]).issubset(official):
            raise ValueError("Official license candidates changed: "+r["entity_id"])
        if any(r.get(k) is not False for k in ("official_legal_name_link_verified","payment_branch_verified","individual_attendance_verified")):
            raise ValueError("Review registry must not promote legal/payment/attendance identity")
        if r["merchant"]=="석갈비" and r.get("spending_source_address_verified") is not False:
            raise ValueError("Seokgalbi original public expense address remains unverified")
        if r["merchant"]=="오리오리" and r.get("official_history_continuity_verified") is not False:
            raise ValueError("Interleaved expense labels cannot establish legal continuity")
        rows.append({"entity_id":r["entity_id"],"merchant":r["merchant"],"region":r["region"],
          "original_address":r["original_address"],"official_business_names":r["expected_official_license_names"],
          "assessment":r["assessment"],"research_note":r["analysis"],
          "supporting_urls":[e["url"] for e in r["independent_evidence"]],
          "official_legal_name_link_verified":False,"payment_branch_verified":False,"individual_attendance_verified":False})
    if len(rows)!=9 or len(set(x["entity_id"] for x in rows))!=9:
        raise ValueError("Expected nine unique discrepancy cases")
    return {"checked_at":registry["checked_on"],"official_source_sha256_by_region":expected,
      "resolution":"VENUE_ALIAS_EVIDENCE_ONLY_NO_LEGAL_IDENTITY_PROMOTION",
      "assessment_counts":dict(Counter(r["assessment"] for r in rows)),
      "cases":rows}
def main():
    p=argparse.ArgumentParser();p.add_argument("--audit",required=True);p.add_argument("--registry",required=True);p.add_argument("--output",required=True);a=p.parse_args()
    result=build(json.loads(Path(a.audit).read_text(encoding="utf-8")),json.loads(Path(a.registry).read_text(encoding="utf-8")))
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result["assessment_counts"],ensure_ascii=False))
if __name__=="__main__":main()
