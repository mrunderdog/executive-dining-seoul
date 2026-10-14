#!/usr/bin/env python3
"""Offline validation of published venues against downloaded official restaurant-license CSV.

Input is a UTF-8/CP949 CSV exported from official LOCALDATA / data.go.kr.
No paid API or network is needed. Never infer card-merchant identity from licenses.
"""
from __future__ import annotations
import argparse,csv,json,re,codecs
from pathlib import Path
from difflib import SequenceMatcher

ROOT=Path(__file__).resolve().parents[1]
NAME=("사업장명","업소명","상호명","사업장명칭")
ADDRESS=("도로명전체주소","도로명주소","도로명주소명","소재지전체주소","소재지주소")
STATUS=("영업상태명","영업상태","영업상태코드명","상세영업상태명")
PERMIT=("인허가일자","인허가일","허가일자")

def field(row,names):
    return next((str(row.get(k) or "").strip() for k in names if str(row.get(k) or "").strip()),"")
def normalize(x):
    return re.sub(r"[^0-9가-힣a-z]","",str(x or "").lower().replace("서울특별시","서울").replace("서울시","서울"))
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
    for row in raw:
        key=normalize(field(row,NAME))
        if key in lookup:candidates[key].append(row)
    result=[]
    for v in venues:
        name=normalize(v["merchant"])
        address=normalize(v["address"])
        matches=candidates.get(name,[])
        same_address=[r for r in matches if normalize(field(r,ADDRESS))==address and address]
        matched=same_address[0] if len(same_address)==1 else None
        result.append({
            "merchant":v["merchant"],"address":v["address"],
            "license_match_status":"EXACT_NAME_AND_ADDRESS" if matched else ("AMBIGUOUS_LICENSE_RECORDS" if len(same_address)>1 else "NOT_MATCHED"),
            "license_name":field(matched,NAME) if matched else None,
            "license_address":field(matched,ADDRESS) if matched else None,
            "license_business_status":field(matched,STATUS) if matched else None,
            "license_permit_date":field(matched,PERMIT) if matched else None,
            "name_candidate_count":len(matches),"exact_name_address_count":len(same_address),
            "payment_branch_verified":False,"personal_attendance_verified":False,
        })
    return result
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True,help="Previously downloaded official restaurant licence CSV")
    p.add_argument("--output",default=str(ROOT/"reports/restaurant-license-audit.json"))
    args=p.parse_args()
    venues=json.loads((ROOT/"sources/police_verified_expense_venues.json").read_text(encoding="utf-8"))["venues"]
    rows=evaluate(venues,load_official(Path(args.input)))
    out={"official_csv":Path(args.input).name,"total_venues":len(rows),
         "exact_business_and_address_matches":sum(x["license_match_status"]=="EXACT_NAME_AND_ADDRESS" for x in rows),
         "policy":"A restaurant licence verifies restaurant identity/status only, not the payment card branch or attendee.",
         "venues":rows}
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"total":len(rows),"exact":out["exact_business_and_address_matches"],"output":str(dest)},ensure_ascii=False))
if __name__=="__main__":main()
