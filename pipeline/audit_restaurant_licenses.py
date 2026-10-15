#!/usr/bin/env python3
"""Offline validation of published venues against downloaded official restaurant-license CSV.

Input is a UTF-8/CP949 CSV exported from official LOCALDATA / data.go.kr.
No paid API or network is needed. Never infer card-merchant identity from licenses.
"""
from __future__ import annotations
import argparse,csv,json,re,hashlib,urllib.request,urllib.parse,tempfile,datetime
from pathlib import Path
from difflib import SequenceMatcher
from localdata_regions import route_localdata, building_key, registry_codes

ROOT=Path(__file__).resolve().parents[1]
NAME=("사업장명","업소명","상호명","사업장명칭")
ADDRESS=("도로명전체주소","도로명주소","도로명주소명","소재지전체주소","소재지주소")
STATUS=("영업상태명","영업상태","영업상태코드명","상세영업상태명")
PERMIT=("인허가일자","인허가일","허가일자")

def field(row,names):
    return next((str(row.get(k) or "").strip() for k in names if str(row.get(k) or "").strip()),"")
def normalize(x):
    return re.sub(r"[^0-9가-힣a-z]","",str(x or "").lower().replace("서울특별시","서울").replace("서울시","서울"))
def road_building_key(address):
    return building_key(address)

def load_official(path:Path):
    """Stream official multi-million row CSV without materializing the whole file."""
    with path.open("rb") as fh:
        sample=fh.read(65536)
    encoding="utf-8-sig"
    try: sample.decode(encoding)
    except UnicodeDecodeError: encoding="cp949"
    with path.open("r",encoding=encoding,newline="",errors="strict") as fh:
        reader=csv.DictReader(fh)
        header=reader.fieldnames or []
        if not any(n in header for n in NAME) or not any(n in header for n in ADDRESS):
            raise ValueError("Missing official restaurant licensing name/address columns")
        for row in reader:
            yield row

def evaluate(venues,raw):
    lookup={}
    for v in venues:
        lookup.setdefault(normalize(v["merchant"]),[]).append(v)
    # Store only rows that match one of the 18 approved merchants.
    candidates={name:[] for name in lookup}
    # Reverse-search official licenses by actual road/building number, even when
    # the expense merchant is a corporate name or abbreviated chain label.
    target_keys={road_building_key(v["address"]) for v in venues}
    target_keys.discard("")
    address_candidates={key:[] for key in target_keys}
    for row in raw:
        key=normalize(field(row,NAME))
        if key in lookup:candidates[key].append(row)
        building=road_building_key(field(row,ADDRESS))
        if building in target_keys:
            address_candidates[building].append(row)
    result=[]
    for v in venues:
        name=normalize(v["merchant"])
        address=normalize(v["address"])
        matches=candidates.get(name,[])
        same_address=[r for r in matches if normalize(field(r,ADDRESS))==address and address]
        building_key=road_building_key(v["address"])
        same_building=[r for r in matches if building_key and road_building_key(field(r,ADDRESS))==building_key]
        pool=same_address if same_address else same_building
        matched=pool[0] if len(pool)==1 else None
        match_status=("EXACT_NAME_AND_ADDRESS" if len(same_address)==1 else
                      "NAME_AND_BUILDING_ADDRESS_FLOOR_UNVERIFIED" if len(same_building)==1 else
                      "AMBIGUOUS_LICENSE_RECORDS" if len(pool)>1 else "NOT_MATCHED")
        neighbors=address_candidates.get(building_key,[])
        # Business names at the address are *investigation candidates* only.
        # A shared building cannot by itself identify the restaurant/licensee.
        hint=normalize(v.get("display") or v["merchant"])
        ranked=sorted(neighbors,key=lambda x:(
            SequenceMatcher(None,normalize(field(x,NAME)),hint).ratio(),
            normalize(field(x,NAME))),reverse=True)
        candidate_entries=[{
            "license_name":field(x,NAME),
            "license_address":field(x,ADDRESS),
            "license_business_status":field(x,STATUS),
            "license_permit_date":field(x,PERMIT),
            "identical_merchant":normalize(field(x,NAME))==name,
            "same_building_only_not_verified_identity":True
        } for x in ranked[:40]]
        result.append({
            "merchant":v["merchant"],"address":v["address"],
            "official_building_businesses":candidate_entries,
            "official_building_business_count":len(neighbors),
            "official_building_businesses_truncated":len(neighbors)>40,
            "license_match_status":match_status,
            "license_name":field(matched,NAME) if matched else None,
            "license_address":field(matched,ADDRESS) if matched else None,
            "license_business_status":field(matched,STATUS) if matched else None,
            "license_permit_date":field(matched,PERMIT) if matched else None,
            "name_candidate_count":len(matches),"exact_name_address_count":len(same_address),
            "same_building_address_count":len(same_building),
            "floor_or_unit_proven":bool(same_address),
            "payment_branch_verified":False,"personal_attendance_verified":False,
        })
    return result
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",help="Previously downloaded official restaurant licence CSV")
    p.add_argument("--fetch-official",action="store_true")
    p.add_argument("--scope",choices=["police","all"],default="police")
    p.add_argument("--regions",default="서울서대문구,서울중구,서울종로구,서울서초구",help="Comma-separated registry region keys; do not guess codes")
    p.add_argument("--output",default=str(ROOT/"reports/restaurant-license-audit.json"))
    args=p.parse_args()
    codes=registry_codes()
    selected=[x.strip() for x in args.regions.split(",") if x.strip()]
    if not selected or len(selected)!=len(set(selected)) or len(selected)>15:
        p.error("Select 1–15 unique jurisdictions")
    for region in selected:
        if region not in codes or region.endswith("본청") or not re.fullmatch(r"\d{7}",str(codes[region])):
            p.error("Unknown LOCALDATA jurisdiction: "+region)
    allowed=set(selected)
    if args.scope=="police":
        venues=json.loads((ROOT/"sources/police_verified_expense_venues.json").read_text(encoding="utf-8"))["venues"]
    else:
        from data_io import load_payload
        from published_sources import merge_published_sources
        from extra_published import merge_extra_published
        from global_entities import merge_global_entities
        merged=merge_global_entities(merge_extra_published(merge_published_sources(load_payload())))
        venues=[]
        for r in merged.get("records") or []:
            address=str(r.get("address") or "")
            region=route_localdata(address,codes)
            if not region or region[0] not in allowed or not road_building_key(address):
                continue
            venues.append({"merchant":r.get("name") or "", "display":(r.get("business") or {}).get("display") or r.get("name"),
                           "address":address, "origin":r.get("origin"),"entity_id":r.get("entity_id")})
        # Cross-agency pilot must not silently claim nationwide source coverage.
        if not venues:raise RuntimeError("No addressed published cross-agency venues in four selected districts")
    if not args.input and not args.fetch_official: p.error("Specify --input or --fetch-official")
    if args.input and args.fetch_official: p.error("Input modes are mutually exclusive")
    provenance=[]
    if args.input:
        file=Path(args.input)
        provenance.append({"file":file.name,"sha256":hashlib.sha256(file.read_bytes()).hexdigest()})
        rows=evaluate(venues,load_official(file))
    else:
        districts={name:codes[name] for name in selected}
        with tempfile.TemporaryDirectory() as tmp:
            paths=[]
            for district,code in districts.items():
                url="https://file.localdata.go.kr/file/download/general_restaurants/info?"+urllib.parse.urlencode({"orgCode":code})
                request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Referer":"https://file.localdata.go.kr/file/general_restaurants/info"})
                dest=Path(tmp)/(code+".csv")
                with urllib.request.urlopen(request,timeout=120) as response:
                    content_type=response.headers.get("Content-Type","").lower()
                    if response.status!=200 or not any(x in content_type for x in ("csv","octet-stream","download")):
                        raise RuntimeError("Unexpected official CSV response "+district+": "+content_type)
                    with dest.open("wb") as output:
                        while True:
                            part=response.read(1024*1024)
                            if not part:break
                            output.write(part)
                if dest.stat().st_size<100:raise RuntimeError("Empty official CSV "+district)
                # A community code map is only a hint. Reject downloads where
                # the actual official address rows do not belong to the requested jurisdiction.
                scoped=0
                routable=0
                for official in load_official(dest):
                    address=field(official,ADDRESS)
                    found=route_localdata(address,codes)
                    if found:
                        routable+=1
                        if found[0]==district:scoped+=1
                if scoped==0 or routable==0 or scoped/routable<0.80:
                    raise RuntimeError(
                        f"LOCALDATA jurisdiction mismatch {district}: {scoped}/{routable} officially addressed rows"
                    )
                provenance.append({"district":district,"orgCode":code,"source_url":url,"sha256":hashlib.sha256(dest.read_bytes()).hexdigest(),"bytes":dest.stat().st_size,"jurisdiction_confirmed_rows":scoped,"routable_rows":routable})
                paths.append(dest)
            def chained_rows():
                for file in paths:
                    yield from load_official(file)
            rows=evaluate(venues,chained_rows())
    out={"official_csv":Path(args.input).name if args.input else "LOCALDATA_REGIONAL_BATCH","scope":args.scope,"geographic_scope":selected,"sources":provenance,"checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"total_venues":len(rows),
         "exact_business_and_address_matches":sum(x["license_match_status"]=="EXACT_NAME_AND_ADDRESS" for x in rows),
         "name_and_building_matches":sum(x["license_match_status"]=="NAME_AND_BUILDING_ADDRESS_FLOOR_UNVERIFIED" for x in rows),
         "policy":"A restaurant licence verifies restaurant identity/status only, not the payment card branch or attendee.",
         "venues":rows}
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"total":len(rows),"exact":out["exact_business_and_address_matches"],"building":out["name_and_building_matches"],"sources":len(provenance),"output":str(dest)},ensure_ascii=False))
if __name__=="__main__":main()
