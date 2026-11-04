#!/usr/bin/env python3
"""Public official Uiwang PDF layout evidence; no transactions are published.

The source/download URLs and SHA-256 hashes below were observed in a previous
live ingestion run. Record raw PDF bytes and two independent text extractions
without guessing a missing numeric amount or reconstructing any transaction.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest_council_expense import fetch_binary, workbook_rows, normalize_sheet

SOURCES = [
    {
        "month": 9,
        "url": "https://council.uiwang.go.kr/bbsAttachDownload.do?key=1ab017c72c5f4961632c043b0404a1bec512b9811d482bba563e6ae17ae1183cb37d39e5b3a14b42",
        "sha256": "bc5df5028318f46a62894cd4a08c59472a02a0e105c7599157191ca8d986ba5c",
        "post_url": "https://council.uiwang.go.kr/kr/Information/bbsCost.do?reform=view&key=547eef31959fdf170038fa71233f5388bcf46524e0550bb9994d4f0a43926aa24d4b391e5f24721b&pageNum=1&flag=all&keyword=",
    },
    {
        "month": 8,
        "url": "https://council.uiwang.go.kr/bbsAttachDownload.do?key=42b2c5366f2c05875cf874d5b459ee33bc9aed47fe9a14592bc85b3c52ef51f63a7b570c532bd8e1",
        "sha256": "e175375b752fdc70b408a5a0dce22cf4317358c4780935496a58ba63b3b4dc58",
        "post_url": "https://council.uiwang.go.kr/kr/Information/bbsCost.do?reform=view&key=6a5c357ad968690a83ec3672c8e7d46e312b6a681669cf0da4914185a77b152695a418bf21c0c165&pageNum=1&flag=all&keyword=",
    },
]

def main():
    from pypdf import PdfReader
    target = Path("reports/recovery/uiwang-pdf-evidence")
    target.mkdir(parents=True, exist_ok=True)
    summary = []
    for spec in SOURCES:
        month = spec["month"]
        record = {"month": month, "attachment_url": spec["url"],
                  "post_url": spec["post_url"], "expected_sha256": spec["sha256"]}
        try:
            blob = fetch_binary(spec["url"], spec["post_url"])
            observed = hashlib.sha256(blob).hexdigest()
            record.update(observed_sha256=observed, size=len(blob))
            if not blob.startswith(b"%PDF"):
                raise ValueError("official attachment did not contain PDF header")
            # A changed official file is forensic evidence, not an authorized
            # replacement for the known source snapshot.
            if observed != spec["sha256"]:
                raise ValueError("official PDF changed SHA; review source version before accepting")
            (target / f"uiwang-2026-{month:02d}-official.pdf").write_bytes(blob)
            reader = PdfReader(io.BytesIO(blob))
            pages = []
            for i, page in enumerate(reader.pages, start=1):
                layout = page.extract_text(extraction_mode="layout") or ""
                plain = page.extract_text() or ""
                rows = []
                for name, extracted in workbook_rows(blob, f"uiwang-2026-{month:02d}.pdf"):
                    if name == f"pdf-page-{i}":
                        rows = extracted
                        break
                meta = {"source": "uiwang", "region": "경기", "jurisdiction": "의왕시",
                        "institution": "의왕시의회", "post_url": spec["post_url"],
                        "attachment_url": spec["url"], "attachment_name": f"uiwang-{month}.pdf",
                        "attachment_sha256": observed, "period": (2026, month, None),
                        "default_role": "의장"}
                normalized, info = normalize_sheet(rows, f"pdf-page-{i}", meta)
                pages.append({"page": i, "layout_text": layout, "plain_text": plain,
                              "split_rows": rows, "parser_info": info,
                              "normalized_count": len(normalized)})
            record["pages"] = pages
            bad_pages = [
                {"page": p["page"], "parser_info": p["parser_info"]}
                for p in pages if p["parser_info"].get("status") != "OK"
            ]
            record["parsed_rows"] = sum(p["normalized_count"] for p in pages)
            record["bad_pages"] = bad_pages
            record["status"] = "PARSER_HOLD" if bad_pages else "CAPTURED"
            (target / f"uiwang-2026-{month:02d}-layout.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            record["status"] = "HOLD"
            record["error"] = f"{type(exc).__name__}: {exc}"
        summary.append({k: v for k, v in record.items() if k != "pages"})
        print(json.dumps(summary[-1], ensure_ascii=False), flush=True)
    (target / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if not all(r.get("status") == "CAPTURED" for r in summary):
        raise SystemExit(2)

if __name__ == "__main__":
    main()
