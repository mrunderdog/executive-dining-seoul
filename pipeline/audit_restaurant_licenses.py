#!/usr/bin/env python3
"""Offline validation of published venues against downloaded official restaurant-license CSV.

Input is a UTF-8/CP949 CSV exported from official LOCALDATA / data.go.kr.
No paid API or network is needed. Never infer card-merchant identity from licenses.
"""
from __future__ import annotations
import argparse,csv,json,re,hashlib,urllib.request,urllib.parse,tempfile,datetime
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
    p.add_argument("--input",help="Previously downloaded official restaurant licence CSV")
    p.add_argument("--fetch-official",action="store_true")
    p.add_argument("--output",default=str(ROOT/"reports/restaurant-license-audit.json"))
    args=p.parse_args()
    venues=json.loads((ROOT/"sources/police_verified_expense_venues.json").read_text(encoding="utf-8"))["venues"]
    if not args.input and not args.fetch_official: p.error("Specify --input or --fetch-official")
    if args.input and args.fetch_official: p.error("Input modes are mutually exclusive")
    provenance=[]
    if args.input:
        file=Path(args.input)
        provenance.append({"file":file.name,"sha256":hashlib.sha256(file.read_bytes()).hexdigest()})
        rows=evaluate(venues,load_official(file))
    else:
        districts={"서울서대문구":"3120000","서울중구":"3010000","서울종로구":"3000000","서울서초구":"3210000"}
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
                provenance.append({"district":district,"orgCode":code,"source_url":url,"sha256":hashlib.sha256(dest.read_bytes()).hexdigest(),"bytes":dest.stat().st_size})
                paths.append(dest)
            def chained_rows():
                for file in paths:
                    yield from load_official(file)
            rows=evaluate(venues,chained_rows())
    out={"official_csv":Path(args.input).name if args.input else "LOCALDATA_FOUR_DISTRICTS","sources":provenance,"checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"total_venues":len(rows),
         "exact_business_and_address_matches":sum(x["license_match_status"]=="EXACT_NAME_AND_ADDRESS" for x in rows),
         "policy":"A restaurant licence verifies restaurant identity/status only, not the payment card branch or attendee.",
         "venues":rows}
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"total":len(rows),"exact":out["exact_business_and_address_matches"],"output":str(dest)},ensure_ascii=False))
if __name__=="__main__":main()
