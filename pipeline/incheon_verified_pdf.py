"""Exact-source Incheon Council PDF parser for five 2026-08/09 attachments.

Only invoked when the source's SHA-256 is one of the public official PDF
digests independently retrieved in GitHub Actions original forensics.
Never silently omit date-bearing rows. Each page must match its verified
structural row count, and the original amount/merchant must be observable.
"""
from __future__ import annotations
import hashlib
import re
from datetime import date

VERIFIED = {
 "d85541d349a5f5e20fb4023be5c34093ad59a7e80483a3409af2c61143ef6dcb": (1320, 8, "환경교통위원장", {"pdf-page-1":15,"pdf-page-2":5}),
 "4856197cef57cff59e5ecb3825e7fad9ed1a88697222a9bdc2da7d1d03bd43f3": (1322, 9, "도시건설위원장", {"pdf-page-1":12}),
 "860248268daf693651bff18e8a3c737acbeb7d123e09629f041ac4540e0d21e8": (1323, 9, "교육위원장", {"pdf-page-1":2}),
 "e1459b54a55c040caa86af3f5fcc582a630543b79cf6030acc86f96153a97e1e": (1326, 9, "의회운영위원장", {"pdf-page-1":12}),
 "44129be489aee23846fa19c4e0de465ef105164be42f74e2a1fe99c06d5b89dd": (1327, 9, "환경교통위원장", {"pdf-page-1":12}),
}
AMOUNT=re.compile(r"^(\d{1,3}(?:,\d{3})+)(.*)$")
DATETIME_JOINED=re.compile(r"^\s*(20\d{2})[.\-](\d{2})[.\-](\d{2})\.?\s*(\d{2}:\d{2})(.+)$")
DATE_ONLY=re.compile(r"^20\d{2}-\d{2}-\d{2}$")

def normalize_verified_incheon(rows, sheet, meta):
    from ingest_council_expense import clean_text, valid_transaction_merchant, parse_amount, parse_people
    sha=meta.get("attachment_sha256")
    if sha not in VERIFIED:
        return [],{"status":"UNKNOWN_PDF_SHA","sheet":sheet}
    seq,month,role,expected_pages=VERIFIED[sha]
    expected=expected_pages.get(sheet)
    if expected is None or meta.get("source")!="incheon_council":
        return [],{"status":"UNKNOWN_PAGE","sheet":sheet,"seq":seq}
    if meta.get("period") not in ([2026,month,None],(2026,month,None)):
        return [],{"status":"OFFICIAL_PERIOD_MISMATCH","sheet":sheet,"seq":seq}
    parsed,errors,subtotal=None,[],None
    parsed=[]
    total_text=None
    for ri,cells in enumerate(rows,1):
        values=[clean_text(c) for c in cells if clean_text(c)]
        if not values:continue
        first=values[0]
        if first.startswith(("2026년","2026년도","20269년","(단위","(:","사 용 일 시","일자","일","계(")):
            if first.startswith("계("):
                if len(values)==2 and re.fullmatch(r"\d{1,3}(?:,\d{3})+",values[1]):
                    total_text=int(values[1].replace(",",""))
                else:errors.append({"row":ri,"reason":"invalid_subtotal","cells":values})
            continue
        if first in ("(단위: 원)","(단위 :","집행일시") or ("금" in values and "액" in values):
            continue
        # Two different, actual public PDF layouts:
        # - 1320/1322/1327: date+time+purpose may be concatenated,
        #   and amount+merchant may be concatenated.
        # - 1323/1326: separate date, time, amount and merchant columns.
        dt=DATETIME_JOINED.match(first)
        if dt:
            yy,mm,dd,clock,purpose_lead=dt.groups()
            try:used=date(int(yy),int(mm),int(dd)).isoformat()
            except ValueError:
                errors.append({"row":ri,"reason":"calendar_date","cells":values});continue
            tail=values[1:]
            # Find amount prefix with a comma-grouped observed integer.
            pair=None
            for i,v in enumerate(tail):
                matched=AMOUNT.match(v)
                if matched:
                    pair=(i,matched)
                    break
            if not pair:
                errors.append({"row":ri,"reason":"missing_explicit_amount","cells":values});continue
            amount_index,amount_match=pair
            people_token=tail[amount_index-1] if amount_index>0 else ""
            purpose=" ".join([purpose_lead,*tail[:max(0,amount_index-1)]])
            amount_text=amount_match.group(1)
            merchant=amount_match.group(2).strip()
            remaining=tail[amount_index+1:]
            if not merchant and remaining:
                merchant=remaining.pop(0)
            # Exact observed 1320 PDF issue: original merchant and the word
            # '카드' sometimes lack a separator. Remove only a terminal token
            # when a separate card column is absent, retaining original evidence
            # in parser metadata (no invented merchant name).
            method="카드" if remaining and remaining[-1]=="카드" else ""
            if merchant.endswith("카드") and not method:
                merchant=merchant[:-2].strip()
                method="카드"
            people=parse_people(people_token) if people_token not in ("-","") else None
        elif DATE_ONLY.match(first) and len(values)==8:
            # 1326 has separate columns: date, time, purpose, participants,
            # amount, venue, method; eight raw cells in source extraction?
            # Handle actual extraction based on observed amount position.
            used=first;clock=values[1];purpose=values[2]
            people=parse_people(values[3])
            amount_text=values[4];merchant=values[5];method=values[6]
        elif DATE_ONLY.match(first) and len(values)==7:
            used=first;clock=values[1]
            if seq==1323:
                purpose=values[2];merchant=values[3];people=parse_people(values[4])
                amount_text=values[5];method=values[6]
            else:
                purpose=values[2];people=parse_people(values[3])
                amount_text=values[4];merchant=values[5];method=values[6]
        else:
            errors.append({"row":ri,"reason":"unexpected_nonheader_row","cells":values});continue
        if not used.startswith(f"2026-{month:02d}-") or not re.fullmatch(r"\d{2}:\d{2}",clock):
            errors.append({"row":ri,"reason":"invalid_date_or_time","cells":values});continue
        if not re.fullmatch(r"\d{1,3}(?:,\d{3})+",amount_text):
            errors.append({"row":ri,"reason":"malformed_amount","cells":values});continue
        amt=parse_amount(amount_text)
        if not amt or not 0<amt<50_000_000 or not valid_transaction_merchant(merchant):
            errors.append({"row":ri,"reason":"amount_or_merchant","cells":values});continue
        record={
            "region":meta["region"],"jurisdiction":meta["jurisdiction"],
            "institution":meta["institution"],"source_key":meta["source"],
            "source_post_url":meta["post_url"],"source_attachment_url":meta["attachment_url"],
            "source_attachment_name":meta["attachment_name"],"source_period":meta["period"],
            "source_sheet":sheet,"source_row":ri,
            "used_date":used,"used_time":clock,"date_inferred_from_previous_row":False,
            "role":role,"merchant":merchant,"address":"","purpose":purpose,
            "people":people,"amount":amt,"amount_inferred_from_row":False,
            "payment_method":method,"parse_confidence":"high",
        }
        record["row_id"]=hashlib.sha256("|".join(str(record.get(k,"")) for k in
            ("institution","used_date","role","merchant","amount","source_sheet","source_row")).encode("utf-8")).hexdigest()[:20]
        parsed.append(record)
    amount_sum=sum(r["amount"] for r in parsed)
    if len(parsed)!=expected:
        errors.append({"reason":"expected_official_page_rows_mismatch",
                       "expected":expected,"observed":len(parsed)})
    if total_text is not None and total_text!=amount_sum:
        errors.append({"reason":"printed_subtotal_mismatch","expected":total_text,"observed":amount_sum})
    return parsed,{"status":"ROW_PARSE_GAPS" if errors else "OK",
                   "sheet":sheet,"parser":"incheon_sha_locked_2026_pdf_v1",
                   "source_seq":seq,"parsed_rows":len(parsed),"expected_rows":expected,
                   "parsed_total":amount_sum,"printed_total":total_text,
                   "unparsed_transaction_like_rows":len(errors),
                   "unparsed_examples":errors[:12]}
