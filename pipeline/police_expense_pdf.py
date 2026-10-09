"""Strict PDF table parser for disclosed senior Police Agency expense *user*.

A posting's '사용자' identifies the budget/expense user, NOT proof they personally
attended the meal. Output is always staging-only, pending business/address QA.
"""
from __future__ import annotations

import hashlib
import io
import re
from datetime import date
from urllib.parse import urlsplit

def compact(value):
    return re.sub(r"\s+","",str(value or ""))

def _value(value):
    return " ".join(str(value or "").split())

def parse_expense_table(table:list[list], role:str, official_pdf_url:str, sha256:str) -> tuple[list[dict],dict]:
    host=(urlsplit(official_pdf_url).hostname or "").lower()
    if urlsplit(official_pdf_url).scheme!="https" or host not in {"www.police.go.kr","police.go.kr"}:
        raise ValueError("Police expense PDF must originate at exact official domain")
    role_key=compact(role)
    if not role_key:raise ValueError("Missing source-title senior role")
    header=next((i for i,row in enumerate(table)
                 if len(row)>=7 and "사용자" in compact(row[0])
                 and "일자" in compact(row[1]) and "사용처" in compact(row[3])),None)
    if header is None:raise ValueError("Missing expected police expense table header")
    matched_user=False
    expected_count=None
    expected_total=None
    result=[]
    for ix,raw in enumerate(table[header+1:],header+1):
        if len(raw)<7:continue
        if raw[0] and role_key in compact(raw[0]):
            matched_user=True
        daystr=_value(raw[1])
        if daystr=="소 계":
            mm=re.search(r"(\d+)건",_value(raw[2]))
            expected_count=int(mm.group(1)) if mm else None
            try:expected_total=int(compact(raw[4]).replace(",",""))
            except ValueError:expected_total=None
            continue
        if not re.fullmatch(r"20\d\d-\d\d-\d\d",daystr):continue
        try:day=date.fromisoformat(daystr)
        except ValueError:continue
        try:amount=int(compact(raw[4]).replace(",",""))
        except ValueError:continue
        merchant=_value(raw[3])
        purpose=_value(raw[2])
        if not merchant or not purpose or amount<=0 or day.year>date.today().year:continue
        person_count=None
        try:person_count=int(compact(raw[5]))
        except (ValueError,TypeError):pass
        result.append({
            "row_id":hashlib.sha256(f"{sha256}:{ix}".encode()).hexdigest()[:24],
            "source_key":"national_police","institution":"경찰청",
            "cohort":"police_leadership","role":role,
            "role_source":"official_posting_and_pdf_user_column",
            "source_url":official_pdf_url,
            "pdf_sha256":sha256,"source_row":ix,
            "used_date":day.isoformat(),"merchant":merchant,"purpose":purpose,
            "amount":amount,"people":person_count,
            "actor_evidence":"EXPLICIT_PDF_USER_COLUMN",
            "attendance_evidence":"NOT_ESTABLISHED",
            "publication_status":"STAGING_ONLY",
        })
    if not matched_user:
        raise ValueError("Posting role not found in PDF user column")
    if expected_count is None or expected_total is None:
        raise ValueError("Missing official transaction subtotal control")
    computed_total=sum(r["amount"] for r in result)
    if len(result)!=expected_count or computed_total!=expected_total:
        raise ValueError(f"PDF control mismatch: {len(result)}/{expected_count} records, {computed_total}/{expected_total} won")
    return result,{"records":len(result),"amount_total":computed_total,
                   "document_count":expected_count,"document_amount_total":expected_total,
                   "attendance_proved":False,"publication_enabled":False}

def parse_pdf(blob:bytes, role:str, official_pdf_url:str) -> tuple[list[dict],dict]:
    if not blob.startswith(b"%PDF-"):raise ValueError("Not a PDF")
    from pdfplumber import open as open_pdf
    sha=hashlib.sha256(blob).hexdigest()
    rows=[]
    summaries=[]
    with open_pdf(io.BytesIO(blob)) as doc:
        if len(doc.pages)>25:raise ValueError("Unexpectedly long Police Agency PDF")
        for page in doc.pages:
            for table in page.extract_tables():
                if not table or not any("사용자" in compact(line[0]) for line in table if line):
                    continue
                chunk,summary=parse_expense_table(table,role,official_pdf_url,sha)
                rows.extend(chunk)
                summaries.append(summary)
    if not rows:raise ValueError("No reconciled official Police Agency transaction table found")
    return rows,{"pdf_sha256":sha,"pages_parsed":len(summaries),
                 "records":len(rows),"amount_total":sum(x["amount"] for x in rows),
                 "attendance_proved":False,"publication_enabled":False}
