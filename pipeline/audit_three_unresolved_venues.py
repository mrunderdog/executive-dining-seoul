#!/usr/bin/env python3
"""Evidence-only follow-up for three unresolved LOCALDATA merchant identities.

Checks the distinct official rest_cafes industry for Vintage204 and retains
the source/identity boundary for OriOri and Seokgalbi. Never writes public
venue addresses or establishes a card merchant / individual attendance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from audit_restaurant_licenses import load_official, field, NAME, ADDRESS, STATUS, PERMIT, normalize
from localdata_regions import building_key, route_localdata, registry_codes

ROOT=Path(__file__).resolve().parents[1]
TARGETS={
    "오리오리":("f6507f4fea32a880","서울관악구"),
    "빈티지204":("69914cda326f3ca2","서울은평구"),
    "석갈비":("4dbe7d20166679e9","충남보령시"),
}
COLLECTED=("management_id","관리번호","인허가관리번호")

def check_cafe_file(path:Path, region="서울은평구") -> dict:
    codes=registry_codes()
    name_hits=[]
    same_building=[]
    routable=0
    correct_region=0
    target_building=building_key("서울 은평구 은평로 193-1",codes)
    for row in load_official(path):
        name=field(row,NAME)
        address=field(row,ADDRESS)
        route=route_localdata(address,codes)
        if route:
            routable+=1
            if route[0]==region:correct_region+=1
        if route is None or route[0]!=region:
            continue
        is_name=normalize(name)==normalize("빈티지204")
        is_building=building_key(address,codes)==target_building
        if not (is_name or is_building):
            continue
        item={"licensed_name":name,"licensed_address":address,
              "status":field(row,STATUS),"permit_date":field(row,PERMIT),
              "match_type":("EXACT_NAME_AND_BUILDING" if is_name and is_building else
                            "SAME_NAME_OTHER_BUILDING" if is_name else "OTHER_NAME_SAME_BUILDING")}
        if is_name:name_hits.append(item)
        if is_building:same_building.append(item)
    # Prevent accidentally accepting a download for a different district.
    if not routable or not correct_region or correct_region/routable<0.80:
        raise ValueError(f"Invalid official rest_cafes region: {correct_region}/{routable}")
    exact=[r for r in same_building if r["match_type"]=="EXACT_NAME_AND_BUILDING"]
    if len(exact)==1:
        status="OFFICIAL_REST_CAFE_NAME_AND_BUILDING_MATCH"
    elif exact:
        status="OFFICIAL_REST_CAFE_AMBIGUOUS_RECORDS"
    elif name_hits:
        status="OFFICIAL_REST_CAFE_NAME_OTHER_LOCATION"
    elif same_building:
        status="OFFICIAL_REST_CAFE_OTHER_LICENSES_SAME_BUILDING"
    else:
        status="OFFICIAL_REST_CAFE_NO_MATCH"
    return {
        "status":status,
        "matched_name_anywhere_in_district":name_hits[:20],
        "official_entries_at_target_building":same_building[:20],
        "same_name_same_building_count":len(exact),
        "official_routable_rows":routable,
        "official_region_rows":correct_region,
        "official_region_ratio":round(correct_region/routable,6),
        "source_url":"https://file.localdata.go.kr/file/download/rest_cafes/info?orgCode="+codes[region],
        "official_csv_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
        "official_csv_bytes":path.stat().st_size
    }

def check_three(audit:dict, cafe:dict, registry:dict, enterprise:dict) -> dict:
    lookup={r["merchant"]:r for r in audit.get("venues",[]) if r.get("merchant") in TARGETS}
    cases={r["merchant"]:r for r in registry["entries"] if r.get("merchant") in TARGETS}
    for name,(eid,region) in TARGETS.items():
        row=lookup.get(name);reg=cases.get(name)
        if not row or not reg or row.get("entity_id")!=eid or row.get("region")!=region:
            raise ValueError("Unexpected official audit or registration identity: "+name)
        if row.get("license_match_status")!="NOT_MATCHED":
            raise ValueError("Changed match outcome; manual recheck needed: "+name)
        if any(reg.get(k) is not False for k in ("official_legal_name_link_verified","payment_branch_verified","individual_attendance_verified")):
            raise ValueError("Registry promoted an unproven identity")
    expense_candidates=[x for x in enterprise.get("candidates",[]) if x.get("merchant")=="석갈비"]
    if len(expense_candidates)!=1:
        raise ValueError("Cannot uniquely trace Seokgalbi expense source")
    spending=expense_candidates[0]
    expense_rows=[r for r in spending.get("recent",[]) if r.get("date")=="2025-07-29" and r.get("institution")=="한국중부발전"]
    if not expense_rows:
        raise ValueError("Original publicly disclosed Seokgalbi transaction not found")
    ori=lookup["오리오리"]
    seok=lookup["석갈비"]
    result={
      "schema_version":"1.0",
      "policy":"License and spend source provenance are independent; never link legal permit, card merchant or a person without direct matching evidence.",
      "source_provenance":audit.get("sources",[]),
      "cases":[
        {"merchant":"오리오리","entity_id":ori["entity_id"],
         "status":"DIFFERENT_GOVERNMENT_SPENDING_LABELS_NO_LICENSE_HISTORY",
         "official_current_license_names":[x["license_name"] for x in ori["official_building_businesses"]],
         "expense_source_pages":[x["url"] for x in cases["오리오리"].get("independent_evidence",[]) if x["type"].startswith("official_expense_")],
         "comment":"Official Gwanak spending lists show both 오리오리 and 요리요리 interleaved across 2024–2026, including August 2026, at the same address. No direct evidence links their legal licence identities."},
        {"merchant":"빈티지204","entity_id":lookup["빈티지204"]["entity_id"],
         "status":cafe["status"],"official_rest_cafes":cafe,
         "comment":"Official rest-cafe registration is a separate industry from general restaurants. Even exact name/address is not evidence of a particular card terminal."},
        {"merchant":"석갈비","entity_id":seok["entity_id"],
         "status":"MULTIPLE_SAME_BUILDING_LICENSES_NO_PAYMENT_ID",
         "competing_official_licenses":[{"licensed_name":r["license_name"],"licensed_address":r["license_address"],
                                         "license_status":r["license_business_status"],"permit_date":r["license_permit_date"]}
                                        for r in seok.get("official_building_businesses",[])],
         "source_expense":[{"date":r["date"],"institution":r["institution"],"merchant":"석갈비",
                            "amount":r.get("amount"),"source":r["source"]} for r in expense_rows],
         "spending_source_address":None,"spending_source_address_verified":False,
         "candidate_venue_location_from_separate_listing":True,
         "comment":"Original Korea Midland Power expense candidate has no address or telephone. The Boryeong address came from a separate business listing and cannot establish the paid venue or licensed legal merchant."}
      ]
    }
    for case in result["cases"]:
        case.update({"legal_merchant_identity_verified":False,
                     "payment_branch_verified":False,"individual_attendance_verified":False})
    return result

def fetch_rest_cafes(dest:Path):
    code=registry_codes()["서울은평구"]
    url=f"https://file.localdata.go.kr/file/download/rest_cafes/info?orgCode={code}"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Referer":"https://file.localdata.go.kr/file/rest_cafes/info"})
    with urllib.request.urlopen(req,timeout=80) as response:
        ctype=response.headers.get("Content-Type","").lower()
        if response.status!=200 or not any(x in ctype for x in ("csv","octet-stream","download")):
            raise ValueError("Unexpected official rest_cafes content-type "+ctype)
        with dest.open("wb") as output:
            total=0
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                total+=len(chunk)
                if total>150_000_000: raise ValueError("Unexpected huge official district file")
                output.write(chunk)
    if dest.stat().st_size<100:raise ValueError("Empty official cafe file")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",required=True)
    p.add_argument("--registry",required=True)
    p.add_argument("--enterprise",required=True)
    p.add_argument("--rest-cafe-csv")
    p.add_argument("--fetch-official-rest-cafes",action="store_true")
    p.add_argument("--output",required=True)
    a=p.parse_args()
    if bool(a.rest_cafe_csv)==a.fetch_official_rest_cafes:
        p.error("Choose exactly one of --rest-cafe-csv and --fetch-official-rest-cafes")
    with tempfile.TemporaryDirectory() as tmp:
        csv_path=Path(a.rest_cafe_csv) if a.rest_cafe_csv else Path(tmp)/"eunpyeong-rest-cafes.csv"
        if a.fetch_official_rest_cafes:fetch_rest_cafes(csv_path)
        cafe=check_cafe_file(csv_path)
    output=check_three(
        json.loads(Path(a.audit).read_text(encoding="utf-8")),
        cafe,
        json.loads(Path(a.registry).read_text(encoding="utf-8")),
        json.loads(Path(a.enterprise).read_text(encoding="utf-8"))
    )
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":[(r["merchant"],r["status"]) for r in output["cases"]],
       "rest_cafe_csv_sha256":cafe["official_csv_sha256"]},ensure_ascii=False))

if __name__=="__main__":main()
