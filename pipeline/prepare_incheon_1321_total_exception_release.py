#!/usr/bin/env python3
"""Incheon 1321 row-level scan release, printed grand total EXPLICITLY UNRECONCILED.

No merchant recommendations. Old evidence, including the original PDF extraction
error, is immutable; a same-file SHA-backed exception is used ONLY for transient
incremental QA. Never mark the complete official document as reconciled.
"""
from __future__ import annotations
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
from collections import Counter

from build_source_candidates import build_candidates
from capital_backfill import canonical_attachment_url
from guard_full_council import check_integrity
from qa_council_publication import assess_incremental, period_bounds

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data/raw/incheon_council_expense.json"
DISC=ROOT/"reports/capital-backfill-discovery-incheon_council.json"
CAND=ROOT/"reports/incheon_council-executive-candidates.json"
EVIDENCE=ROOT/"pipeline/incheon_1321_official_total_exception_evidence.json"
EXPECTED_PDF="1ed8414992e06999cfb60c12e23c1d72ccff041941007aa0145012cb4c5a927e"
EXPECTED_PNG="bbf13022f9045b9a28078540a5eaaef812c08628ca116d67dfeb3257ef3471d2"

def stop(reason):
    raise ValueError("STOP: "+reason)

def stage():
    ev=json.loads(EVIDENCE.read_text(encoding="utf-8"))
    old_bytes=RAW.read_bytes()
    disc_bytes=DISC.read_bytes()
    cand_bytes=CAND.read_bytes()
    base=json.loads(old_bytes)
    discovery=json.loads(disc_bytes)
    if base.get("source")!="incheon_council" or len(base["rows"])!=274 or len(base["files"])!=12:stop("baseline changed")
    if len(discovery["posts"])!=22:stop("discovery changed")
    if not (ev["msg_seq"]==1321 and ev["official_pdf_sha256"]==EXPECTED_PDF
            and ev["render_png_sha256"]==EXPECTED_PNG
            and ev["official_pdf_bytes"]==73642
            and ev["source_page_count"]==1
            and ev["printed_row_count"]==len(ev["transactions"])==10
            and ev["individual_row_sum_krw"]==929200
            and ev["printed_grand_total_krw"]==1367400
            and ev["printed_minus_row_sum_krw"]==438200
            and ev["source_grand_total_status"]=="HOLD_INCONSISTENT_OFFICIAL_PRINTED_TOTAL"
            and ev["financial_aggregation_approved"] is False
            and ev["all_rows_ranking_eligible"] is False):stop("unsafe or altered source exception")
    source_url=canonical_attachment_url(ev["official_url"])
    authorized_posts=[p for p in discovery["posts"] if p.get("source")=="incheon_council" and
                      any(canonical_attachment_url(a.get("url"))==source_url for a in p.get("attachments",[]))]
    if len(authorized_posts)!=1:stop("official scan missing or ambiguous discovery")
    source_post=authorized_posts[0]
    baseline_errors=[e for e in base.get("errors",[]) if canonical_attachment_url(e.get("url"))==source_url]
    if len(baseline_errors)!=1 or baseline_errors[0].get("error")!="ValueError: PDF contained no extractable text rows":
        stop("historical scan extraction failure changed")
    if source_url in {canonical_attachment_url(f["url"]) for f in base["files"]}:stop("source already published")
    if base["source_recovery"].get("scanned_documents_remaining_on_hold")!=1:stop("historical scan hold changed")
    already={r["row_id"] for r in base["rows"]}
    new=[]
    for n,tx in enumerate(ev["transactions"],1):
        if tx["line"]!=n:stop("source line numbers invalid")
        when=dt.date.fromisoformat(tx["date"])
        if (when.year,when.month)!=(2026,8):stop("source month mismatch")
        clock=dt.time.fromisoformat(tx["time"])
        if clock.strftime("%H:%M")!=tx["time"]:stop("source time mismatch")
        if not (tx["merchant"] and tx["purpose"] and tx["printed_place"] and
                isinstance(tx["amount"],int) and tx["amount"]>0 and
                isinstance(tx["people"],int) and tx["people"]>0 and
                tx["printed_payment_method"]=="신용카드" and
                tx["recommendation_eligible"] is False):stop("unverified merchant/purpose/amount")
        row={
            "region":"인천","jurisdiction":"인천광역시","institution":"인천광역시의회",
            "source_key":"incheon_council",
            "source_post_url":source_post["post_url"],
            "source_attachment_url":ev["official_url"],
            "source_attachment_name":source_post["attachments"][0]["text"],
            "source_period":[2026,8,None],
            "source_sheet":"scanned-pdf-page-1-rowlevel-only",
            "source_row":n,"used_date":tx["date"],"used_time":tx["time"],
            "date_inferred_from_previous_row":False,"role":ev["role"],
            "merchant":tx["merchant"],"address":"",
            "printed_venue_address_text":tx["printed_place"],
            "purpose":tx["purpose"],"people":tx["people"],
            "amount":tx["amount"],"amount_inferred_from_row":False,
            "payment_method":tx["printed_payment_method"],
            "expense_kind":tx["record_kind"],
            "parse_confidence":"manual_visual_sha_pinned_row_level",
            "source_page":1,"official_original_sha256":EXPECTED_PDF,
            "row_level_status":"VERIFIED_OFFICIAL_TOTAL_UNRECONCILED",
            "printed_total_reconciliation":"HOLD_438200_KRW_OFFICIAL_DISCREPANCY",
            "date_quality":"source_verified_unranked",
            "recommendation_status":"HOLD_UNRECONCILED_OFFICIAL_TOTAL_AND_PAYMENT_BRANCH",
            "ranking_eligible":False,
        }
        row["row_id"]=hashlib.sha256(
            f"incheon_council|scan_1321|{n}|{tx['date']}|{tx['time']}|{tx['merchant']}|{tx['amount']}".encode()
        ).hexdigest()[:20]
        if row["row_id"] in already:stop("duplicate historic row identifier")
        already.add(row["row_id"])
        new.append(row)
    if len(new)!=10 or sum(r["amount"] for r in new)!=929200:stop("printed source transaction sum mismatch")
    proposed=copy.deepcopy(base)
    proposed["rows"]+=new
    proposed["files"].append({
        "title":source_post["title"],
        "url":ev["official_url"],"name":source_post["attachments"][0]["text"],
        "bytes":ev["official_pdf_bytes"],"sha256":EXPECTED_PDF,
        "sheets":[{"sheet":"scanned-pdf-page-1-rowlevel-only",
                   "status":"ROW_LEVEL_VERIFIED_OFFICIAL_TOTAL_HOLD",
                   "parsed_rows":10,"unparsed_transaction_like_rows":0,
                   "source_verification":"MANUAL_VISUAL_SHA256_PINNED",
                   "printed_transactions":10,
                   "verified_row_amount_sum_krw":929200,
                   "printed_document_total_krw":1367400,
                   "source_total_discrepancy_krw":438200,
                   "full_document_reconciliation":"HOLD"}]
    })
    proposed["row_count"]=284
    proposed["new_files"]=1
    proposed["refresh_mode"]="rowlevel_source_only_official_total_discrepancy"
    proposed["generated_at"]=dt.datetime.now(dt.timezone.utc).isoformat()
    prior=copy.deepcopy(base.get("source_recovery") or {})
    prior.update({
        "status":"INCOMPLETE_2026_08_SCANNED_OFFICIAL_TOTAL_RECONCILIATION",
        "august_1321":"10_VERIFIED_INDIVIDUAL_ROWS_NOT_TOTAL_RECONCILED",
        "august_1321_row_sum_krw":929200,
        "august_1321_official_printed_total_krw":1367400,
        "august_1321_unexplained_gap_krw":438200,
        "august_1321_original_extraction_error":"RETAINED_AND_ATTESTED_MANUAL_ROW_ONLY",
        "new_transaction_ranking_eligible":False,
        "scanned_documents_remaining_on_hold":1,
    })
    # Do not remove the 1321 HOLD exception just because its printed rows are
    # now present: total reconciliation is not complete.
    if len(prior["excluded_official_documents"])!=1 or prior["excluded_official_documents"][0]["msg_seq"]!=1321:stop("HOLD status disappeared")
    prior["excluded_official_documents"][0]["decision"]="ROW_LEVEL_10_PUBLISHED_UNRANKED; FULL_DOCUMENT_TOTAL_STILL_UNRECONCILED"
    prior["unresolved_scanned_disclosures"][0]["decision"]="ROW_LEVEL_10_PUBLISHED_UNRANKED; 438200_KRW_DISCREPANCY_STILL_OPEN"
    proposed["source_recovery"]=prior
    q=copy.deepcopy(base.get("raw_quality") or {})
    q["rows"]=q["transaction_rows"]=284
    valid=0;valid_period=0
    for row in proposed["rows"]:
        try: date=dt.date.fromisoformat(str(row.get("used_date") or ""))
        except (TypeError,ValueError):continue
        valid+=1
        bounds=period_bounds(row.get("source_period"))
        if bounds and bounds[0]<=date<=bounds[1]:valid_period+=1
    q["valid_date_coverage"]=q["all_row_valid_date_coverage"]=round(valid/284,4)
    q["in_period_date_coverage"]=q["all_row_in_period_date_coverage"]=round(valid_period/284,4)
    proposed["raw_quality"]=q
    integrity=check_integrity("incheon_council",proposed,base)
    if integrity["status"]!="PASS":stop("immutable financial ledger failed "+str(integrity["failures"]))
    # An unchanged historic PDF text-extraction error is retained in the ledger.
    # It is superseded in the QA-only copy by the independent verified manual
    # row transcription of the identical SHA-pinned source.
    qaview=copy.deepcopy(proposed)
    qaview["errors"]=[e for e in qaview["errors"]
                      if canonical_attachment_url(e.get("url"))!=source_url]
    if len(qaview["errors"])!=len(base["errors"])-1 or proposed["errors"]!=base["errors"]:
        stop("historical errors removed or unrelated errors suppressed")
    qa=assess_incremental("incheon_council",qaview,discovery,base,discovery)
    if qa["status"]!="PUBLISH_READY" or qa.get("verified_rows")!=10 or qa.get("failures"):
        stop("incremental strict QA failed "+str(qa))
    cand_before=build_candidates("incheon_council")[1]
    RAW.write_text(json.dumps(proposed,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    try:
        cand_after=build_candidates("incheon_council")[1]
        if cand_after!=cand_before or CAND.read_bytes()!=cand_bytes or DISC.read_bytes()!=disc_bytes:
            stop("previous ranking or official discovery changed")
    except Exception:
        RAW.write_bytes(old_bytes)
        raise
    print(json.dumps({
        "status":"ROW_LEVEL_SOURCE_ONLY_TOTAL_EXCEPTION_HOLD",
        "old_rows":274,"new_rows":10,"staged_rows":284,
        "verified_row_amount_krw":929200,
        "printed_total_krw":1367400,
        "unreconciled_gap_krw":438200,
        "new_official_files":1,"total_files":13,
        "strict_qa_rows":"10/10","strict_qa":qa["status"],
        "integrity":integrity["status"],
        "historical_extraction_error_preserved":True,
        "whole_document_reconciled":False,"new_rankings":0,
        "full_source_coverage":False,"publish":False,
    },ensure_ascii=False),flush=True)

if __name__=="__main__":
    stage()
