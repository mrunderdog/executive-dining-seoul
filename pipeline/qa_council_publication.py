#!/usr/bin/env python3
"""Fail-closed official-council date/amount/provenance publication gate.

No files are changed. GitHub Actions may commit source data only after this
command exits successfully; a partial success ratio is never publishable.
"""
from __future__ import annotations

import argparse
import calendar
import json
import re
from datetime import date
from pathlib import Path

from capital_backfill import canonical_attachment_url
from ingest_council_expense import valid_transaction_merchant

ROOT = Path(__file__).resolve().parents[1]


def period_bounds(period):
    if not isinstance(period, (tuple, list)) or len(period) != 3:
        return None
    year, month, quarter = period
    if not isinstance(year, int) or not (2000 <= year <= 2100):
        return None
    if month is not None and isinstance(month, int) and 1 <= month <= 12 and quarter is None:
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    if quarter is not None and isinstance(quarter, int) and 1 <= quarter <= 4 and month is None:
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        return date(year, start_month, 1), date(year, end_month, calendar.monthrange(year, end_month)[1])
    return None


def assess(source: str, data: dict, discovery: dict, min_rows: int = 5) -> dict:
    failures = []
    rows = data.get("rows") or []
    files = data.get("files") or []
    posts = [p for p in discovery.get("posts", []) if p.get("source") == source and p.get("post_url")]
    authorized = {
        canonical_attachment_url(a.get("url"))
        for p in posts for a in p.get("attachments", [])
        if canonical_attachment_url(a.get("url"))
    }
    official = {}
    for item in files:
        u = canonical_attachment_url(item.get("url"))
        if (not u or u not in authorized or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("sha256") or ""))
            or not isinstance(item.get("bytes"), int) or item["bytes"] < 32):
            failures.append("file_not_verified_or_not_in_official_discovery")
            continue
        official[u] = item
    if data.get("source") != source:
        failures.append("source_mismatch")
    if not posts or not official:
        failures.append("missing_official_posts_or_hashed_files")
    if authorized != set(official):
        failures.append("official_attachment_missing_parsed_file")
    if len(rows) < min_rows:
        failures.append("insufficient_transaction_rows")
    if len({r.get("row_id") for r in rows}) != len(rows) or any(not r.get("row_id") for r in rows):
        failures.append("duplicate_or_missing_row_id")

    valid_rows = 0
    bad_examples = []
    known_posts = {p["post_url"] for p in posts}
    for row in rows:
        try:
            used = date.fromisoformat(str(row.get("used_date") or ""))
        except ValueError:
            used = None
        amount = row.get("amount")
        source_url = canonical_attachment_url(row.get("source_attachment_url"))
        bounds = period_bounds(row.get("source_period"))
        valid = (
            row.get("source_key") == source
            and row.get("source_post_url") in known_posts
            and source_url in official
            and valid_transaction_merchant(row.get("merchant"))
            and isinstance(amount, (int, float)) and not isinstance(amount, bool)
            and 0 < amount < 50_000_000
            and used is not None and bounds is not None
            and bounds[0] <= used <= bounds[1]
        )
        if valid:
            valid_rows += 1
        elif len(bad_examples) < 5:
            bad_examples.append({
                "row_id": row.get("row_id"), "date": row.get("used_date"),
                "amount": amount, "source_period": row.get("source_period"),
            })
    if valid_rows != len(rows):
        failures.append("date_amount_or_lineage_invalid_rows")
    # Old pseudo-link failures are retained in legacy raw JSON but are not
    # genuine official attachments. Only errors on a *currently authorized*
    # file identifier can block publication; missing authorized files do too.
    if any(canonical_attachment_url(e.get("url")) in authorized for e in data.get("errors", [])):
        failures.append("unresolved_official_attachment_errors")
    return {
        "source": source,
        "status": "PUBLISH_READY" if not failures else "HOLD",
        "rows": len(rows), "verified_rows": valid_rows,
        "official_posts": len(posts), "verified_files": len(official),
        "coverage": round(valid_rows / len(rows), 5) if rows else 0,
        "failures": sorted(set(failures)), "bad_examples": bad_examples,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--min-rows", type=int, default=5)
    args = ap.parse_args()
    raw_path = ROOT / "data" / "raw" / f"{args.source}_expense.json"
    discovery_path = ROOT / "reports" / f"capital-backfill-discovery-{args.source}.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    result = assess(args.source, raw, discovery, args.min_rows)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PUBLISH_READY":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
