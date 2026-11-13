#!/usr/bin/env python3
"""Isolated nine-row manual scan transcription: source-only, fail closed.

Evidence must point to the exact official PDF and independently SHA-verified
render artifact. No change to old rows, existing rankings, or public venues.
"""
import copy
import datetime
import hashlib
import json
from collections import Counter
from pathlib import Path

from guard_full_council import check_integrity
from qa_council_publication import assess_incremental
from build_source_candidates import build_candidates

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/"pipeline/incheon_1329_scanned_transcription.json"
RAW=ROOT/"data/raw/incheon_council_expense.json"
DISC=ROOT/"reports/capital-backfill-discovery-incheon_council.json"
CAND=ROOT/"reports/incheon_council-executive-candidates.json"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def create():
    ev=json.loads(EVIDENCE.read_text(encoding="utf-8"))
    old_bytes,disc_bytes,cand_bytes=RAW.read_bytes(),DISC.read_bytes(),CAND.read_bytes()
    base=json.loads(old_bytes)
    orig_disc=json.loads(disc_bytes)
    original=copy.deepcopy(base)
    assert base["source"]=="incheon_council"
    assert len(base["rows"])==265 and len(base["files"])==11
    assert len(orig_disc["posts"])==22
    assert ev["msg_seq"]==1329 and ev["official_pdf_sha256"]=="81e2d85f2dd0c5c43463da8e34fa724d38223790921f657c49a2fb480886e264"
    assert ev["official_pdf_bytes"]==58020
    assert ev["verified_render_sha256"]=="8b118761607f64cb3d15a6a197ec120801dd0af050207ebbcb3eb7bfd8b2625e"
    assert ev["source_render_artifact_id"]==13908307185
    assert ev["printed_transaction_count"]==len(ev["transactions"])==9
    assert ev["individual_row_sum_krw"]==ev["grand_total_printed_krw"]==784000
    assert ev["meal_row_count"]==8 and ev["non_meal_amount_krw"]==300000
    assert [t["line"] for t in ev["transactions"]]==list(range(1,10))
    assert ev["record_status"]=="SOURCE_VERIFIED_UNRANKED"
    assert ev["full_source_coverage"] is False and ev["source_payee_card_merchant_identity_verified"] is False
    assert ev["other_document_hold"]["msg_seq"]==1321 and ev["other_document_hold"]["quarantined"] is True
    if ev["official_pdf_sha256"] in {x.get("sha256") for x in base["files"]}:
        raise ValueError("1329 already in canonical source ledger")
    official=next((p for p in orig_disc["posts"] if any(a.get("url")==ev["official_attachment_url"]
                  for a in p.get("attachments",[]))),None)
    if not official or official["post_url"]!=ev["official_post_url"]:
        raise ValueError("1329 not in official unchanged discovery")
    existing_ids={r["row_id"] for r in base["rows"]}
    new=[]
    seen=set()
    for t in ev["transactions"]:
        date=datetime.date.fromisoformat(t["date"])
        assert (date.year,date.month)==(2026,9)
        assert t["time"]==datetime.time.fromisoformat(t["time"]).strftime("%H:%M")
        assert t["merchant"] and isinstance(t["amount"],int) and 0<t["amount"]<50_000_000
        assert t["kind"] in ("MEAL","REFRESHMENT_PURCHASE_NOT_DINING_VISIT")
        if t["line"]==6:
            assert t["amount"]==300000 and t["kind"]!="MEAL"
            assert t["merchant"]=="안스베이커리"
            assert t["people"] is None
            assert "다과구입" in t["purpose"]
        else:
            assert t["kind"]=="MEAL" and isinstance(t["people"],int) and t["people"]>0
        rec={
            "region":"인천","jurisdiction":"인천광역시",
            "institution":"인천광역시의회","source_key":"incheon_council",
            "source_post_url":official["post_url"],
            "source_attachment_url":ev["official_attachment_url"],
            "source_attachment_name":official["attachments"][0]["text"],
            "source_period":[2026,9,None],
            "source_sheet":"scanned-pdf-page-1-manual",
            "source_row":t["line"],
            "used_date":t["date"],"used_time":t["time"],
            "date_inferred_from_previous_row":False,
            "role":ev["role"],"merchant":t["merchant"],
            "address":"","printed_venue_address_text":t["printed_place"],
            "purpose":t["purpose"],"people":t["people"],
            "amount":t["amount"],"amount_inferred_from_row":False,
            "payment_method":"신용카드",
            "parse_confidence":"visually_verified_sha_pinned_original",
            "expense_kind":t["kind"],
            "source_page":1,
            "official_original_sha256":ev["official_pdf_sha256"],
            "source_verified_identity":"PDF_EXPENSE_PAYEE_NAME_ONLY_NOT_PAYMENT_BRANCH_VERIFIED",
            "date_quality":"source_verified_unranked",
            "recommendation_status":"HOLD_PAYMENT_BRANCH_UNVERIFIED",
            "ranking_eligible":False,
        }
        rec["row_id"]=hashlib.sha256((
            "incheon_council|scanned_pdf_1329|"+str(t["line"])+"|"+t["date"]+
            "|"+t["time"]+"|"+t["merchant"]+"|"+str(t["amount"])).encode()).hexdigest()[:20]
        if rec["row_id"] in existing_ids or rec["row_id"] in seen:
            raise ValueError("old/new row-id collision")
        seen.add(rec["row_id"])
        new.append(rec)
    assert len(new)==9 and sum(x["amount"] for x in new)==784000
    after=copy.deepcopy(base)
    after["rows"]+=new
    after["files"].append({
        "title":official["title"],
        "url":ev["official_attachment_url"],
        "name":official["attachments"][0]["text"],
        "bytes":ev["official_pdf_bytes"],
        "sha256":ev["official_pdf_sha256"],
        "sheets":[{"sheet":"scanned-pdf-page-1-manual",
                   "status":"OK","parsed_rows":9,"unparsed_transaction_like_rows":0,
                   "source_verification":"SHA_PINNED_ORIGINAL_VISUAL_TRANSCRIPTION",
                   "individual_amount_total_krw":784000,
                   "printed_amount_total_krw":784000,
                   "transactions_not_dining_visits":1}],
    })
    after["row_count"]=274
    after["new_files"]=1
    after["refresh_mode"]="source_only_scanned_verified_partial"
    after["generated_at"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
    after["source_recovery"]={
        **copy.deepcopy(base["source_recovery"]),
        "scope":"PARTIAL_2026_08_09_OFFICIAL_SOURCE",
        "status":"INCOMPLETE_2026_08_SCANNED_COMMITTEE_DISCLOSURE",
        "september_scan_1329":"VERIFIED_9_ROWS_784000_KRW_SOURCE_ONLY",
        "september_scan_1329_historical_error":"PRESERVED_AS_RESOLVED_BY_SHA_ATTESTED_MANUAL_TRANSCRIPTION",
        "added_verified_scan_transactions":9,
        "added_verified_scan_total_krw":784000,
        "new_transaction_ranking_eligible":False,
        "unresolved_scanned_disclosures":[
           {"msg_seq":1321,"period":"2026-08",
            "status":"QUARANTINE_PRINTED_TOTAL_DISCREPANCY",
            "difference_krw":438200,"publish":False}],
    }
    oldq=base.get("raw_quality") or {}
    q=copy.deepcopy(oldq)
    q["rows"]=q["transaction_rows"]=274
    valid=0;inperiod=0
    from qa_council_publication import period_bounds
    for row in after["rows"]:
        try: used=datetime.date.fromisoformat(str(row.get("used_date") or ""))
        except (ValueError,TypeError): continue
        valid+=1
        bounds=period_bounds(row.get("source_period"))
        if bounds and bounds[0]<=used<=bounds[1]:inperiod+=1
    q["valid_date_coverage"]=q["all_row_valid_date_coverage"]=round(valid/274,4)
    q["in_period_date_coverage"]=q["all_row_in_period_date_coverage"]=round(inperiod/274,4)
    after["raw_quality"]=q
    integrity=check_integrity("incheon_council",after,base)
    # Original historical errors are immutable evidence. The 1329 text-
    # extraction failure has been superseded by independently SHA-verified
    # manual transcription of the image-only original. Suppress it in a
    # transient QA *view* only, never in the committed source.
    qaview=copy.deepcopy(after)
    historic1329=[x for x in qaview.get("errors",[])
                 if x.get("url")==ev["official_attachment_url"]]
    if (len(historic1329)!=1
        or historic1329[0].get("error")!="ValueError: PDF contained no extractable text rows"):
        raise ValueError("STOP: historical 1329 error not exactly attested")
    qaview["errors"]=[x for x in qaview["errors"]
                     if x.get("url")!=ev["official_attachment_url"]]
    if len(qaview["errors"])!=len(base.get("errors",[]))-1:
        raise ValueError("STOP: unrelated historical errors changed")
    if not any("msg_seq=1321" in x.get("url","") for x in qaview["errors"]):
        raise ValueError("STOP: unresolved August 1321 error silently hidden")
    qa=assess_incremental("incheon_council",qaview,orig_disc,base,orig_disc)
    if integrity["status"]!="PASS" or qa["status"]!="PUBLISH_READY" or qa.get("verified_rows")!=9:
        raise ValueError(f"STOP strict QA/integrity {qa} {integrity}")
    if after["rows"][:265]!=base["rows"] or after["files"][:11]!=base["files"]:
        raise ValueError("immutable historical ledger changed")
    before_candidates=build_candidates("incheon_council")[1]
    RAW.write_text(json.dumps(after,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    try:
        new_candidates=build_candidates("incheon_council")[1]
        if new_candidates!=before_candidates or CAND.read_bytes()!=cand_bytes or DISC.read_bytes()!=disc_bytes:
            raise ValueError("ranking/discovery unexpectedly changed")
    except Exception:
        RAW.write_bytes(old_bytes)
        raise
    assert RAW.read_bytes()!=old_bytes and len(new_candidates)==len(before_candidates)
    print(json.dumps({
      "status":"PARTIAL_SOURCE_ONLY_READY",
      "previous_rows":265,"proposed_rows":274,"new_verified_scanned_rows":9,
      "new_amount_krw":784000,"food_visit_rows_without_branch_verification":8,
      "non_dining_refreshment_rows":1,"non_dining_amount_krw":300000,
      "original_file_sha":sha(old_bytes),"existing_discovery_sha":sha(disc_bytes),
      "original_candidate_sha":sha(cand_bytes),
      "source_qa":qa["status"],"data_integrity":integrity["status"],
      "published_recommendation_count_unchanged":len(new_candidates),
      "other_august_scan_hold":True,"publish":False
    },ensure_ascii=False),flush=True)

if __name__=="__main__":
    create()
