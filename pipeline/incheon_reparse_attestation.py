#!/usr/bin/env python3
"""Incheon old NO_HEADER provenance: attest, never overwrite historical files.

For incremental financial-source QA only, build a disposable *view* of five
unchanged PDF file entries using verified same-run source parser observations.
The persisted data/raw baseline and every historical sheet remain immutable.
No certification is permitted for scans, changed SHA, partial rows or gaps.
"""
from __future__ import annotations
import copy
import hashlib
import json
from collections import Counter

from capital_backfill import canonical_attachment_url

LEGACY_SEQUENCES=frozenset({1320,1322,1323,1326,1327})
VALID_PAGE_STATES=frozenset({"OK","DUPLICATE_OFFICIAL_PAGE_NO_NEW_ROWS"})


def seq_from_url(url):
    import re
    m=re.search(r"(?:[?&])msg_seq=(\d+)(?:&|$)",url or "")
    return int(m.group(1)) if m else None


def attest_legacy_files(baseline, forensic, independent):
    """Return an audit proof and an immutable-original-preserving QA-only map.

    All five historical PDFs are required, not only the subset available in a
    particular workflow. Each SHA/row/amount/page observation must match the
    independently established official source expectations.
    """
    old={canonical_attachment_url(f.get("url")):f for f in baseline.get("files",[])}
    docs={int(d["msg_seq"]):d for d in forensic.get("documents",[])}
    expected={int(x["msg_seq"]):x for x in independent.get("files",[])}
    failures=[]
    proven={}
    for seq in sorted(LEGACY_SEQUENCES):
        reference=expected.get(seq)
        doc=docs.get(seq)
        if not reference or not doc:
            failures.append(f"attestation_missing_official_{seq}")
            continue
        url=canonical_attachment_url(doc.get("url"))
        historic=old.get(url)
        if not historic or seq_from_url(historic.get("url"))!=seq:
            failures.append(f"attestation_missing_historic_file_{seq}")
            continue
        if not any(p.get("status")=="NO_HEADER" for p in historic.get("sheets",[])):
            failures.append(f"attestation_historic_status_changed_{seq}")
        if (not doc.get("sha256") or
            doc.get("sha256")!=reference.get("sha256") or
            doc.get("sha256")!=historic.get("sha256") or
            doc.get("bytes")!=historic.get("bytes") or
            doc.get("exceptions") or
            doc.get("pdf_page_count")!=reference.get("pages") or
            len(doc.get("pages",[]))!=reference.get("pages")):
            failures.append(f"attestation_identity_or_page_count_{seq}")
            continue
        pages=doc["pages"]
        source_rows=doc.get("staged_full_rows") or []
        if (len(source_rows)!=reference.get("transactions") or
            len({r.get("row_id") for r in source_rows})!=len(source_rows) or
            sum(int(r.get("amount") or 0) for r in source_rows)!=reference.get("amount_total_krw")):
            failures.append(f"attestation_transaction_reconciliation_{seq}")
            continue
        normalized_pages=[]
        for number,p in enumerate(pages,1):
            current=p.get("current_parser") or {}
            if (p.get("sheet")!=f"pdf-page-{number}" or
                p.get("normalized_count")!=current.get("parsed_rows") or
                current.get("status") not in VALID_PAGE_STATES or
                (current.get("unparsed_transaction_like_rows") or 0)!=0 or
                "parser_exception" in p):
                failures.append(f"attestation_page_unverified_{seq}_{number}")
            normalized_pages.append({**copy.deepcopy(current),"sheet":p["sheet"]})
        if sum(x.get("parsed_rows",0) for x in normalized_pages)!=len(source_rows):
            failures.append(f"attestation_page_row_coverage_{seq}")
        if seq==1320 and [p.get("parsed_rows") for p in normalized_pages]!=[15,5]:
            failures.append("attestation_1320_headerless_page_gap")
        if not any(err.endswith(f"_{seq}") or err.startswith(f"attestation_page_unverified_{seq}_")
                   for err in failures):
            certified_file=copy.deepcopy(historic)
            certified_file["sheets"]=normalized_pages
            proven[url]={
                "msg_seq":seq,"official_url":url,
                "official_sha256":reference["sha256"],
                "baseline_sha256":historic["sha256"],
                "size_bytes":historic["bytes"],
                "original_sheet_statuses":[p.get("status") for p in historic["sheets"]],
                "attested_page_statuses":[p.get("status") for p in normalized_pages],
                "attested_page_transactions":[p.get("parsed_rows") for p in normalized_pages],
                "transactions":len(source_rows),
                "amount_total_krw":reference["amount_total_krw"],
                "sha256_of_attested_file_metadata":hashlib.sha256(
                    json.dumps(certified_file,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
                "qa_view_file":certified_file,
            }
    if set(seq_from_url(url) for url in proven)!=LEGACY_SEQUENCES:
        failures.append("attestation_five_legacy_files_not_complete")
    audit={
        "status":"PASS" if not failures else "HOLD",
        "attested_files":len(proven),
        "expected_legacy_files":len(LEGACY_SEQUENCES),
        "total_attested_transactions":sum(p["transactions"] for p in proven.values()),
        "old_file_metadata_mutated":False,
        "scope":"QA_ONLY_LEGACY_SOURCE_REPARSE",
        "failures":sorted(set(failures)),
        "files":[{k:v for k,v in proof.items() if k!="qa_view_file"}
                 for proof in sorted(proven.values(),key=lambda x:x["msg_seq"])],
    }
    # Fail closed, so a partial certification is not inadvertently usable.
    if failures: return audit,{}
    return audit,{url:proof["qa_view_file"] for url,proof in proven.items()}


def make_attested_qa_view(proposed, certified_files, attestation):
    """Use only for assess_incremental; NEVER commit this shadow file metadata."""
    if attestation.get("status")!="PASS" or len(certified_files)!=len(LEGACY_SEQUENCES):
        raise ValueError("unverified or partial attestation")
    temporary=copy.deepcopy(proposed)
    matches=0
    for i,file in enumerate(temporary.get("files",[])):
        url=canonical_attachment_url(file.get("url"))
        if url in certified_files:
            approved=certified_files[url]
            if file.get("sha256")!=approved.get("sha256"):
                raise ValueError("attested QA view does not match original SHA")
            temporary["files"][i]=copy.deepcopy(approved)
            matches+=1
    if matches!=len(LEGACY_SEQUENCES):
        raise ValueError("attested QA view missing old files")
    return temporary
