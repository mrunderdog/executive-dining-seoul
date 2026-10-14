"""Conservative evidence semantics for public-expense restaurant signals.

A transaction attributed to an office, role or department does not prove
that any specific public official visited or attended.
"""
from __future__ import annotations

EXPLICIT_ATTENDANCE="EXPLICIT_PERSON_ATTENDANCE"
EXPENSE_ONLY="DISCLOSED_EXPENSE_OR_USAGE"
UNSPECIFIED="UNCLASSIFIED"

def classify_record(record:dict)->dict:
    evidence=record.get("evidence") or {}
    raw=int(evidence.get("visits") or 0)
    spending=int(evidence.get("spending_events") or 0)
    # No supported cohort has directly documented personal attendance at present.
    # A future explicit-attendance classification must be made from source-specific
    # proof, not an automatic conversion of historical "visits" counters.
    return {
        "source_event_count":raw+spending,
        "reported_usage_events":raw,
        "disclosed_spending_events":spending,
        "confirmed_person_attendances":0,
        "personal_attendance_status":"NOT_ESTABLISHED",
        "classification":EXPENSE_ONLY if (raw or spending) else UNSPECIFIED,
        "method_note":"집행·사용처 공개 건수이며 특정 공직자의 현장 참석을 증명하지 않음",
    }

def apply_evidence_semantics(payload:dict)->dict:
    for record in payload.get("records") or []:
        record["evidence_semantics"]=classify_record(record)
    meta=payload.setdefault("meta",{})
    meta["attendance_policy"]="Transaction and usage events are not verified personal attendance"
    return payload
