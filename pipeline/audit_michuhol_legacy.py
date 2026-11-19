#!/usr/bin/env python3
"""Read-only audit of one historical Michuhol official PDF ZIP.

The legacy ingestion used a PDF header-to-cell mapping that frequently stored
attendee counts as merchants. This probe does not modify or publish records.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from ingest_council_expense import fetch_binary, normalize_sheet, workbook_rows

ROOT = Path(__file__).resolve().parents[1]


def audit(month: str, save_attachment: str | None = None, attachment_file: str | None = None) -> dict:
    year, month_number = (int(v) for v in month.split("-"))
    if not (2024 <= year <= 2030 and 1 <= month_number <= 12):
        raise ValueError("Invalid historical month")
    raw = json.loads((ROOT / "data/raw/michuhol_expense.json").read_text(encoding="utf-8"))
    discovery = json.loads((ROOT / "reports/capital-backfill-discovery-michuhol.json").read_text(encoding="utf-8"))
    posts = [p for p in discovery["posts"] if p.get("source") == "michuhol"
             and p.get("period", [])[:2] == [year, month_number] and p.get("attachments")]
    if len(posts) != 1 or len(posts[0]["attachments"]) != 1:
        raise ValueError(f"Expected one official post and attachment for {month}, found {len(posts)} posts")
    post = posts[0]
    attachment = post["attachments"][0]
    original = [r for r in raw["rows"] if r.get("source_period", [])[:2] == [year, month_number]]
    if not original:
        raise ValueError(f"No baseline transactions for {month}")
    metadata = {
        "source": "michuhol", "region": "인천", "jurisdiction": "미추홀구",
        "institution": "미추홀구의회", "period": [year, month_number, None],
        "post_url": post["post_url"], "attachment_url": attachment["url"],
        "attachment_name": attachment.get("text", ""), "default_role": "",
    }
    blob = (Path(attachment_file).read_bytes() if attachment_file else
            fetch_binary(attachment["url"], post["post_url"]))
    digest = hashlib.sha256(blob).hexdigest()
    historical_files = [f for f in raw["files"] if f.get("url") == attachment["url"]]
    expected_digest = historical_files[0].get("sha256", "") if len(historical_files) == 1 else ""
    source_unchanged = bool(expected_digest and digest == expected_digest)
    if save_attachment:
        p = ROOT / save_attachment
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)
    recovered, sheets = [], []
    for sheet_name, lines in workbook_rows(blob, attachment.get("text") or "official.zip"):
        parsed, info = normalize_sheet(lines, sheet_name, metadata)
        sheets.append(info)
        recovered.extend(parsed)

    # Date, amount, role and source-sheet coordinates must match each legacy
    # transaction before its merchant is eligible for replacement.
    keys = ("source_sheet", "source_row", "used_date", "amount", "role")
    ledger = lambda r: tuple(str(r.get(k) or "") for k in keys)
    old_counts = Counter(ledger(r) for r in original)
    new_counts = Counter(ledger(r) for r in recovered)
    unaccounted = list((old_counts - new_counts).elements())
    added = list((new_counts - old_counts).elements())
    gaps = sum(s.get("unparsed_transaction_like_rows", 0) for s in sheets)
    bad_sheets = [s.get("sheet") for s in sheets if s.get("status") not in {"OK", "NO_ROWS"}]
    matching = (source_unchanged and len(recovered) >= len(original)
                and not unaccounted and not gaps and not bad_sheets
                and len({ledger(r) for r in recovered}) == len(recovered))
    return {
        "month": month, "status": ("RECONCILED_WITH_ADDITIONS" if added else "RECONCILED") if matching else "HOLD",
        "official_post": post["post_url"], "official_attachment": attachment["url"],
        "official_attachment_bytes": len(blob),
        "official_attachment_sha256": digest,
        "committed_attachment_sha256": expected_digest,
        "official_attachment_sha256_matches_committed": source_unchanged,
        "legacy_rows": len(original), "recovered_rows": len(recovered),
        "unparsed_transaction_like_rows": gaps, "bad_sheets": bad_sheets,
        "unaccounted_legacy": unaccounted[:30], "new_unmatched": added[:30],
        "legacy_false_merchants": sum(r.get("merchant", "").startswith(("의원", "의장", "직원", "위원장")) for r in original),
        "sheets": sheets,
        "legacy": [{k: r.get(k) for k in (*keys, "merchant", "row_id")} for r in original],
        "recovered": [{k: r.get(k) for k in (*keys, "merchant", "row_id", "merchant_evidence", "purpose", "people", "payment_method", "used_time")} for r in recovered],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default="2025-04")
    ap.add_argument("--report", default="reports/recovery/michuhol-legacy-audit.json")
    ap.add_argument("--save-attachment", help="Optional official ZIP copy for PDF visual QA")
    ap.add_argument("--attachment-file", help="Read an already downloaded official ZIP (still checks original SHA-256)")
    args = ap.parse_args()
    report = audit(args.month, args.save_attachment, args.attachment_file)
    destination = ROOT / args.report
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items()
                      if k not in {"legacy", "recovered", "sheets"}}, ensure_ascii=False, indent=2))
    # HOLD is a diagnostic finding rather than a failed CI run. No publication.


if __name__ == "__main__":
    main()
