#!/usr/bin/env python3
"""Fail-closed replacement of verified Michuhol legacy merchant fields.

Uses an official-PDF diagnostic artifact; existing row IDs remain stable so
previous published references and future incremental ingestion do not break.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYS = ("source_sheet", "source_row", "used_date", "amount", "role")
REPARSED_FIELDS = ("merchant", "merchant_evidence", "purpose", "people", "payment_method", "used_time")


def identity(row):
    return tuple(str(row.get(k) or "") for k in KEYS)


def reconcile(raw: dict, report: dict) -> tuple[dict, dict]:
    month = report.get("month")
    if report.get("status") not in {"RECONCILED", "RECONCILED_WITH_ADDITIONS"}:
        raise ValueError("Official PDF audit is not reconciled; HOLD")
    if not isinstance(month, str) or len(month) != 7 or month[4] != "-":
        raise ValueError("Missing month")
    year, m = (int(v) for v in month.split("-"))
    if not report.get("official_attachment_sha256_matches_committed"):
        raise ValueError("Original official file digest was not verified")
    file_records = [f for f in raw.get("files", []) if f.get("url") == report.get("official_attachment")]
    if len(file_records) != 1 or file_records[0].get("sha256") != report.get("official_attachment_sha256"):
        raise ValueError("Existing official archive digest differs from audited file")
    old = [r for r in raw["rows"] if r.get("source_period", [])[:2] == [year, m]]
    historic = report.get("legacy") or []
    recovered = report.get("recovered") or []
    if len(old) != report.get("legacy_rows") or len(recovered) != report.get("recovered_rows"):
        raise ValueError("Baseline or recovered transaction count differs")
    if (report.get("unparsed_transaction_like_rows") or report.get("bad_sheets")
        or report.get("unaccounted_legacy")):
        raise ValueError("Official PDF contains unresolved transaction lines")
    if len({identity(r) for r in old}) != len(old) or len({identity(r) for r in recovered}) != len(recovered):
        raise ValueError("Ambiguous duplicate source coordinates")
    by_id = {identity(r): r for r in old}
    before = {identity(r): r for r in historic}
    parsed = {identity(r): r for r in recovered}
    if (set(by_id) != set(before) or not set(by_id).issubset(parsed)
        or len(recovered) < len(old)):
        raise ValueError("Original transactions must be fully accounted for")
    for key, row in by_id.items():
        if before[key].get("row_id") != row.get("row_id") or before[key].get("merchant") != row.get("merchant"):
            raise ValueError("Legacy proof does not match committed source rows")
        if row.get("source_attachment_url") != report.get("official_attachment") or row.get("source_post_url") != report.get("official_post"):
            raise ValueError("Legacy source post or attachment differs")
    for row in recovered:
        if row.get("merchant_evidence") != "official_pdf_usage_place_column":
            raise ValueError("Missing official usage-place column evidence")
    for sheet in report.get("sheets") or []:
        if sheet.get("status") not in {"OK", "NO_ROWS"} or sheet.get("unparsed_transaction_like_rows"):
            raise ValueError("Unverified PDF sheet")
    if sum(s.get("parsed_rows", 0) for s in report.get("sheets") or []) != len(recovered):
        raise ValueError("Sheet row count does not match transaction ledger")

    updated = deepcopy(raw)
    changed = 0
    for row in updated["rows"]:
        key = identity(row)
        if key not in by_id or row.get("source_period", [])[:2] != [year, m]:
            continue
        normalized = parsed[key]
        if row["merchant"] != normalized["merchant"]:
            changed += 1
        for field in REPARSED_FIELDS:
            row[field] = normalized.get(field)
        row["amount_inferred_from_row"] = False
        row["parse_confidence"] = "high"

    new_keys = set(parsed) - set(by_id)
    for key in sorted(new_keys):
        row = parsed[key]
        template = next((r for r in old if r.get("source_sheet") == row.get("source_sheet")), old[0])
        added = deepcopy(template)
        for field in (*KEYS, *REPARSED_FIELDS, "row_id"):
            added[field] = row.get(field)
        added["date_inferred_from_previous_row"] = False
        added["amount_inferred_from_row"] = False
        added["parse_confidence"] = "high"
        updated["rows"].append(added)

    # Preserve existing order of same-day records; insert only newly found rows.
    updated["rows"].sort(key=lambda r: str(r.get("used_date") or ""))
    if len({r.get("row_id") for r in updated["rows"]}) != len(updated["rows"]):
        raise ValueError("Duplicate row_id after correction")
    file_records_index = next(i for i, f in enumerate(updated["files"])
                              if f.get("url") == report.get("official_attachment"))
    updated["files"][file_records_index]["sheets"] = report["sheets"]
    updated["row_count"] = len(updated["rows"])
    if isinstance(updated.get("raw_quality"), dict):
        updated["raw_quality"]["rows"] = len(updated["rows"])
        updated["raw_quality"]["transaction_rows"] = len(updated["rows"])
    updated.setdefault("verified_legacy_reconciliations", []).append({
        "month": month, "attachment_sha256": report["official_attachment_sha256"],
        "legacy_rows": len(old), "corrected_merchants": changed,
        "new_rows": len(new_keys), "verified_rows": len(recovered),
    })
    return updated, {"month": month, "original": len(old), "verified": len(recovered),
                     "merchant_corrections": changed, "new_rows": len(new_keys),
                     "total_rows": len(updated["rows"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--apply", action="store_true", help="Write only after all provenance checks pass")
    args = ap.parse_args()
    path = ROOT / "data/raw/michuhol_expense.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    updated, summary = reconcile(raw, report)
    if args.apply:
        path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "APPLIED" if args.apply else "DRY_RUN", **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
