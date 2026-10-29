#!/usr/bin/env python3
"""Fail-closed official-council date/amount/provenance publication gate.

No files are changed. First publication checks the whole source. Subsequent
refreshes can compare against HEAD: unchanged legacy rows remain untouched,
while every new or modified record must pass all checks. Exit 3 means no
material source change and triggers restoration of the committed baseline.
"""
from __future__ import annotations

import argparse
import calendar
import json
import re
import subprocess
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
        # Gapyeong's PDF parser explicitly records transaction-like numbered
        # rows it could not parse. They cannot be silently dropped to create a
        # seemingly green publication. A page with no transactions is allowed,
        # but a row parse gap is a strict publication HOLD.
        if source == "gapyeong" and any(
            sheet.get("status") == "ROW_PARSE_GAPS" or
            (sheet.get("unparsed_transaction_like_rows") or 0) > 0
            for sheet in item.get("sheets",[])
        ):
            failures.append("official_gapyeong_pdf_unparsed_transaction_rows")
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


def assess_incremental(source: str, data: dict, discovery: dict,
                       baseline: dict | None, baseline_discovery: dict | None) -> dict:
    """Verify only newly introduced/changed transactions, retaining legacy rows.

    Historical source files predate the 100% QA policy. Existing immutable
    records are grandfathered *only* while unmodified; any new/changed record
    or file must independently pass the same strict provenance/date/amount gate.
    Silent historical row/file loss is not an acceptable refresh.
    """
    if not baseline or not baseline.get("rows"):
        result = assess(source, data, discovery)
        result["qa_scope"] = "full_first_publication"
        return result

    errors = []
    if data.get("source") != source or baseline.get("source") != source:
        errors.append("source_mismatch")
    old_rows = baseline.get("rows") or []
    rows = data.get("rows") or []
    old_by_id = {r.get("row_id"): r for r in old_rows}
    new_by_id = {r.get("row_id"): r for r in rows}
    if (len(old_by_id) != len(old_rows) or len(new_by_id) != len(rows)
        or None in old_by_id or None in new_by_id):
        errors.append("duplicate_or_missing_row_id")
    if set(old_by_id) - set(new_by_id):
        errors.append("historical_rows_removed")

    old_files = {canonical_attachment_url(f.get("url")): f
                 for f in baseline.get("files", []) if canonical_attachment_url(f.get("url"))}
    new_files = {canonical_attachment_url(f.get("url")): f
                 for f in data.get("files", []) if canonical_attachment_url(f.get("url"))}
    if set(old_files) - set(new_files):
        errors.append("historical_files_removed")
    modified_files = {
        url for url, file in new_files.items()
        if url not in old_files or file.get("sha256") != old_files[url].get("sha256")
    }
    def official_urls(d):
        return {canonical_attachment_url(a.get("url"))
                for p in (d or {}).get("posts", []) if p.get("source") == source
                for a in p.get("attachments", []) if canonical_attachment_url(a.get("url"))}

    new_official = official_urls(discovery) - official_urls(baseline_discovery)
    changed = [r for r in rows if r.get("row_id") not in old_by_id
               or r != old_by_id[r.get("row_id")]
               or canonical_attachment_url(r.get("source_attachment_url")) in modified_files]
    changed_ids = {r.get("row_id") for r in changed}
    urls = modified_files | new_official | {
        canonical_attachment_url(r.get("source_attachment_url")) for r in changed
        if canonical_attachment_url(r.get("source_attachment_url"))
    }
    if not changed and not urls and not errors:
        return {"source": source, "status": "NO_CHANGE", "qa_scope": "incremental",
                "rows": len(rows), "baseline_rows_preserved": len(old_rows),
                "new_or_changed_rows": 0, "verified_rows": 0,
                "verified_files": 0, "coverage": 1.0,
                "failures": [], "bad_examples": []}

    post_sample = []
    for post in discovery.get("posts", []):
        if post.get("source") != source or not post.get("post_url"):
            continue
        subset = [a for a in post.get("attachments", [])
                  if canonical_attachment_url(a.get("url")) in urls]
        if subset:
            post_sample.append({**post, "attachments": subset})

    selected_files = [f for f in data.get("files", [])
                      if canonical_attachment_url(f.get("url")) in urls]
    selected_rows = [r for r in rows
                     if r.get("row_id") in changed_ids
                     or canonical_attachment_url(r.get("source_attachment_url")) in urls]
    selected_errors = [e for e in data.get("errors", [])
                       if canonical_attachment_url(e.get("url")) in urls]
    qa = assess(source, {"source": source, "files": selected_files,
                         "rows": selected_rows, "errors": selected_errors},
                {"posts": post_sample}, min_rows=1)
    if any(not any(canonical_attachment_url(r.get("source_attachment_url")) == url
                   for r in selected_rows) for url in urls):
        errors.append("official_file_without_transaction_rows")
    qa["failures"] = sorted(set(qa["failures"] + errors))
    qa["status"] = "HOLD" if qa["failures"] else "PUBLISH_READY"
    qa["qa_scope"] = "incremental"
    qa["baseline_rows_preserved"] = len(old_rows)
    qa["new_or_changed_rows"] = len(changed)
    qa["rows"] = len(rows)
    return qa


def git_json(ref: str, path: str) -> dict | None:
    proc = subprocess.run(["git", "show", f"{ref}:{path}"],
                          cwd=ROOT, capture_output=True, text=True)
    if proc.returncode:
        return None
    return json.loads(proc.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--min-rows", type=int, default=5)
    ap.add_argument("--baseline-ref", help="Verify only changes versus committed baseline (e.g. HEAD)")
    args = ap.parse_args()
    raw_path = ROOT / "data" / "raw" / f"{args.source}_expense.json"
    discovery_path = ROOT / "reports" / f"capital-backfill-discovery-{args.source}.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    if args.baseline_ref:
        result = assess_incremental(
            args.source, raw, discovery,
            git_json(args.baseline_ref, f"data/raw/{args.source}_expense.json"),
            git_json(args.baseline_ref, f"reports/capital-backfill-discovery-{args.source}.json"),
        )
    else:
        result = assess(args.source, raw, discovery, args.min_rows)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] == "NO_CHANGE":
        raise SystemExit(3)
    if result["status"] != "PUBLISH_READY":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
