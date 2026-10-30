"""Source-exact exception ledger for Gimpo's official quarterly XLSX.

No transactional row is silently dropped: every parsed source row belongs to
published rows or a persistently recorded, fully attributed exception.
Classification requires exact economic matches across independently official
files. Unresolved exceptions are never considered publication-ready.
"""
from __future__ import annotations
from collections import Counter
from datetime import date
from qa_council_publication import period_bounds


def economic_key(row):
    """Require same expenditure, not only matching amount/merchant/date."""
    return tuple(str(row.get(k) or "").strip() for k in (
        "institution", "used_date", "used_time", "role", "merchant",
        "purpose", "amount", "people", "payment_method"
    ))


def within_declared_period(row):
    try:
        d=date.fromisoformat(str(row.get("used_date") or ""))
        bounds=period_bounds(row.get("source_period"))
        return bool(bounds and bounds[0] <= d <= bounds[1])
    except (TypeError, ValueError):
        return False


def reconcile_gimpo(rows):
    """Return publishable rows, full exception audit, and input count.

    Cross-document duplicates can be classified only if an independently
    sourced, in-period record has the exact same economic identity.
    Explicit cash condolences with *no place* are non-dining expenditures,
    not phantom restaurants. Blank-place card expenses stay HOLD.
    """
    in_period_by_key={}
    for row in rows:
        if within_declared_period(row) and row.get("merchant"):
            in_period_by_key.setdefault(economic_key(row),[]).append(row)
    publish=[]
    ledger=[]
    for row in rows:
        decision=None
        matching=[candidate for candidate in in_period_by_key.get(economic_key(row),[])
                  if candidate.get("source_attachment_url") != row.get("source_attachment_url")]
        if not within_declared_period(row):
            if len(matching)==1 and row.get("merchant"):
                decision="EXACT_CROSS_FILE_DUPLICATE"
            else:
                decision="HOLD_SOURCE_PERIOD"
        elif not str(row.get("merchant") or "").strip():
            purpose=str(row.get("purpose") or "")
            payment=str(row.get("payment_method") or "")
            if payment=="현금" and any(x in purpose for x in ("축의금","부의금","위로금","경조사비")):
                decision="NON_DINING_CASH_SUPPORT"
            else:
                decision="HOLD_UNIDENTIFIED_PLACE"
        if decision:
            item={"disposition":decision,
                  "original":row,
                  "evidence_matching_in_period_row":matching[0] if decision=="EXACT_CROSS_FILE_DUPLICATE" else None}
            ledger.append(item)
        else:
            publish.append(row)
    return publish,ledger


def verify_gimpo_ledger(data):
    """Fail closed if source accounting or its exception evidence was changed."""
    errors=[]
    if data.get("source")!="gimpo":
        return ["source_mismatch"]
    ledger=data.get("official_exception_ledger")
    if not isinstance(ledger,list):
        return ["missing_official_exception_ledger"]
    rows=data.get("rows") or []
    ids=[r.get("row_id") for r in rows]
    exception_ids=[x.get("original",{}).get("row_id") for x in ledger]
    all_ids=ids+exception_ids
    if any(not k for k in all_ids) or len(set(all_ids))!=len(all_ids):
        errors.append("duplicate_or_missing_ledger_record_id")
    accounting=data.get("official_source_accounting") or {}
    if accounting.get("source_parsed_rows")!=len(all_ids):
        errors.append("source_row_count_not_reconciled")
    if accounting.get("included_rows")!=len(rows) or accounting.get("exception_rows")!=len(ledger):
        errors.append("source_disposition_counts_not_reconciled")
    reason_counts=Counter(x.get("disposition") for x in ledger)
    if accounting.get("exception_reason_counts")!=dict(reason_counts):
        errors.append("source_reason_counts_not_reconciled")
    by_id={r.get("row_id"):r for r in rows}
    file_map={f.get("url"):f for f in data.get("files",[])}
    for item in ledger:
        r=item.get("original") or {}
        classification=item.get("disposition")
        if r.get("source_attachment_url") not in file_map:
            errors.append("unverified_excluded_file")
        if classification=="EXACT_CROSS_FILE_DUPLICATE":
            match=item.get("evidence_matching_in_period_row")
            if not match or match.get("row_id") not in by_id:
                errors.append("duplicate_without_published_matching_row")
            elif (economic_key(r)!=economic_key(match)
                  or not within_declared_period(match)
                  or within_declared_period(r)
                  or match.get("source_attachment_url")==r.get("source_attachment_url")):
                errors.append("invalid_cross_file_duplicate_evidence")
        elif classification=="NON_DINING_CASH_SUPPORT":
            p=str(r.get("purpose") or "")
            if r.get("merchant") or r.get("payment_method")!="현금" or not any(x in p for x in ("축의금","부의금","위로금","경조사비")):
                errors.append("invalid_non_dining_evidence")
        elif classification in {"HOLD_SOURCE_PERIOD","HOLD_UNIDENTIFIED_PLACE"}:
            errors.append("unresolved_official_transaction_exception")
        else:
            errors.append("unknown_exception_disposition")
    return sorted(set(errors))
