#!/usr/bin/env python3
"""Conservative Police Agency expense-merchant review, never personal visit inference."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STAGED=ROOT/"data/raw/police_expense_staging.json"
VENUES=ROOT/"sources/police_verified_expense_venues.json"
REPORT=ROOT/"reports/police-expense-merchant-review.json"
MARKDOWN=ROOT/"reports/police-expense-merchant-review.md"

def review(staging:dict,manifest:dict)->dict:
    from venue_eligibility import is_non_venue_merchant
    if staging.get("publication_enabled") is not False:
        raise ValueError("Police expenses must remain staging only")
    approved={x.get("merchant"):x for x in manifest.get("venues",[]) if x.get("source_key")=="national_police"}
    grouped=defaultdict(list)
    for x in staging.get("transactions",[]):
        if x.get("publication_status")!="STAGING_ONLY" or x.get("attendance_evidence")!="NOT_ESTABLISHED":
            continue
        key=" ".join(str(x.get("merchant") or "").split())
        if not key:continue
        grouped[key].append(x)
    out=[]
    for merchant,rows in grouped.items():
        unique={r["row_id"]:r for r in rows if r.get("row_id")}
        rows=list(unique.values())
        policy=approved.get(merchant)
        approved_rows=sum(bool(policy and x.get("role")==policy.get("approved_role")
            and x.get("pdf_sha256")==policy.get("source_pdf_sha256")
            and x.get("source_url")==policy.get("official_pdf_url")) for x in rows)
        if approved_rows: status="VENUE_IDENTITY_APPROVED"
        elif is_non_venue_merchant(merchant):status="NON_DINING_OR_GENERIC_BILLER"
        else:status="VENUE_LOCATION_NOT_VERIFIED"
        out.append({"merchant":merchant,"status":status,"transactions":len(rows),
           "amount_won":sum(int(x.get("amount") or 0) for x in rows),
           "expense_user_roles":sorted({x["role"] for x in rows}),
           "first_date":min(x["used_date"] for x in rows),"last_date":max(x["used_date"] for x in rows),
           "publication_authorized":bool(approved_rows),
           "approved_transactions":approved_rows,
           "remaining_review_transactions":len(rows)-approved_rows,
           "attendance_confirmed":False,
           "official_pdfs":sorted({x.get("source_url") for x in rows if x.get("source_url")})})
    out.sort(key=lambda x:(x["status"]!="VENUE_IDENTITY_APPROVED",-x["transactions"],-x["amount_won"],x["merchant"]))
    return {"publication_enabled":False,
      "merchant_count":len(out),
      "staged_transaction_count":sum(x["transactions"] for x in out),
      "status_counts":{status:sum(x["status"]==status for x in out)
                       for status in ("VENUE_IDENTITY_APPROVED","NON_DINING_OR_GENERIC_BILLER","VENUE_LOCATION_NOT_VERIFIED")},
      "caution":"Official senior expense-user is not proof of personal attendance or a confirmed visit.",
      "merchants":out}

def main():
    rows=json.loads(STAGED.read_text(encoding="utf-8"))
    manifest=json.loads(VENUES.read_text(encoding="utf-8"))
    d=review(rows,manifest)
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# 경찰청 업무추진비 사용처 검증 현황","","공식 사용자의 집행 명의만 확인됩니다. 본인의 실제 식사 참석·방문을 뜻하지 않습니다.","",
           f"- 거래: {d['staged_transaction_count']}건",
           f"- 상호: {d['merchant_count']}개","",
           "| 사용처 원문 | 검증 상태 | 집행 건수 | 금액 | 명의자 직책 |",
           "|---|---|---:|---:|---|"]
    for x in d["merchants"]:
        label={"VENUE_IDENTITY_APPROVED":"개별 업소·주소 확인",
               "NON_DINING_OR_GENERIC_BILLER":"비식당/일반 결제처",
               "VENUE_LOCATION_NOT_VERIFIED":"업소·주소 검증 대기"}[x["status"]]
        lines.append(f"| {x['merchant'].replace('|','/')} | {label} | {x['transactions']} | {x['amount_won']:,}원 | {', '.join(x['expense_user_roles'])} |")
    MARKDOWN.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("REVIEW_COUNTS",json.dumps(d["status_counts"],ensure_ascii=False))
    print("REVIEW_TRANSACTIONS",d["staged_transaction_count"],"MERCHANTS",d["merchant_count"])
if __name__=="__main__":main()
