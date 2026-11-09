#!/usr/bin/env python3
"""Fail-closed evidence ledger for the verified 2026-08 Incheon Council scanned PDF.

This is NOT OCR and NOT a transaction parser. The line amounts and printed
total were manually checked against the rendered 1-page official image from
artifact run 41579798147, source file msg_seq=1321. Scan is not a positive
parse result; external confirmation/corrected original is still required.

The source SHA, page count, absence of text layer, and ledger arithmetic are
machine-checked so a changed official document cannot inherit this exception.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_SHA = "1ed8414992e06999cfb60c12e23c1d72ccff041941007aa0145012cb4c5a927e"
OFFICIAL_POST = "https://www.icouncil.go.kr/main/bbs/bbsMsgDetail.do?msg_seq=1321&bcd=infordisc&pgno=1"
OFFICIAL_FILE = "https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&fileno=1&msg_seq=1321"
PRINTED_TOTAL_KRW = 1367400
# Exact row amounts visibly printed in original page, 1-based printed serial.
TRANSCRIBED = [
    (1, "2026-08-03", 131000),
    (2, "2026-08-06", 140000),
    (3, "2026-08-11", 56000),
    (4, "2026-08-11", 52000),
    (5, "2026-08-12", 77000),
    (6, "2026-08-13", 39000),
    (7, "2026-08-14", 69200),
    (8, "2026-08-19", 53000),
    (9, "2026-08-20", 249000),
    (10, "2026-08-20", 63000),
]

def audit(pdf_file: Path) -> dict:
    from pypdf import PdfReader
    data = pdf_file.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if sha != EXPECTED_SHA or not data.startswith(b"%PDF"):
        raise ValueError("original official scanned PDF SHA mismatch; stop")
    reader = PdfReader(pdf_file)
    if len(reader.pages) != 1:
        raise ValueError("unexpected official PDF page count")
    text = reader.pages[0].extract_text() or ""
    if text.strip():
        raise ValueError("PDF now has a text layer; re-evaluate from source")
    serials = [s for s, _, _ in TRANSCRIBED]
    if serials != list(range(1, 11)):
        raise ValueError("duplicate or missing manually transcribed serial")
    sum_rows = sum(amount for _, _, amount in TRANSCRIBED)
    if sum_rows == PRINTED_TOTAL_KRW:
        raise ValueError("expected source mismatch is no longer present")
    return {
        "source": "incheon_council",
        "status": "SOURCE_TOTAL_MISMATCH",
        "publication_authorized": False,
        "evidence_mode": "visual_source_transcription_not_OCR",
        "official_post": OFFICIAL_POST,
        "official_file": OFFICIAL_FILE,
        "source_sha256": sha,
        "source_pdf_pages": len(reader.pages),
        "source_printed_transaction_count": 10,
        "source_printed_total_krw": PRINTED_TOTAL_KRW,
        "visually_transcribed_rows": [
            {"source_serial": n, "used_date": d, "printed_amount_krw": amt}
            for n, d, amt in TRANSCRIBED
        ],
        "transcribed_row_count": len(TRANSCRIBED),
        "sum_printed_line_amounts_krw": sum_rows,
        "unreconciled_difference_krw": PRINTED_TOTAL_KRW - sum_rows,
        "interpretation": "official document internal total discrepancy; no inferred row, amount or adjusted total",
        "release_condition": "corrected official document or independently documented source confirmation",
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.pdf)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "visually_transcribed_rows"}, ensure_ascii=False))

if __name__ == "__main__":
    main()
