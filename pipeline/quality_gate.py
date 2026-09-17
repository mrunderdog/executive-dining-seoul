#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

REQUIRED_RECORD_KEYS = {"name", "origin", "evidence", "business", "type", "search_query"}
ALLOWED_TYPES = {"destination", "executive", "both"}


def pct(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def main() -> None:
    from data_io import load_payload
    from published_sources import merge_published_sources
    from extra_published import merge_extra_published
    payload = merge_extra_published(merge_published_sources(load_payload()))
    meta = payload.get("meta", {})
    records = payload.get("records", [])
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(records, list) or not records:
        errors.append("records must be a non-empty list")

    keys_seen = Counter()
    missing_address = 0
    unknown_category = 0
    bad_evidence = 0

    for idx, r in enumerate(records, start=1):
        missing = sorted(REQUIRED_RECORD_KEYS - set(r))
        if missing:
            errors.append(f"record {idx} missing keys: {', '.join(missing)}")
            continue

        name = str(r.get("name", "")).strip()
        origin = str(r.get("origin", "")).strip()
        if not name or not origin:
            errors.append(f"record {idx} has empty name/origin")
        keys_seen[(name, origin)] += 1

        if r.get("type") not in ALLOWED_TYPES:
            errors.append(f"record {idx} has invalid type: {r.get('type')!r}")
        if r.get("type") in {"destination", "both"} and not r.get("destination"):
            errors.append(f"record {idx} type requires destination data")
        if r.get("type") in {"executive", "both"} and not r.get("executive"):
            errors.append(f"record {idx} type requires executive data")

        if not str(r.get("address", "")).strip():
            missing_address += 1
        category = str((r.get("business") or {}).get("category", "")).strip()
        if not category or "확인 필요" in category:
            unknown_category += 1

        ev = r.get("evidence") or {}
        for field in ("visits", "spend", "people", "months", "evening"):
            val = ev.get(field, 0)
            if not isinstance(val, (int, float)) or val < 0:
                bad_evidence += 1
                errors.append(f"record {idx} invalid evidence.{field}: {val!r}")
                break
        recent = ev.get("recent", [])
        if recent and not isinstance(recent, list):
            errors.append(f"record {idx} evidence.recent must be list")

    duplicates = [f"{name} / {origin}" for (name, origin), c in keys_seen.items() if c > 1]
    if duplicates:
        errors.append("duplicate name+origin records: " + "; ".join(duplicates[:20]))

    total = len(records)
    if total:
        if pct(missing_address, total) > 0.65:
            warnings.append(f"address coverage is low: {total-missing_address}/{total}")
        if pct(unknown_category, total) > 0.60:
            warnings.append(f"category coverage is low: {total-unknown_category}/{total}")

    supplements = sum(1 for r in records if r.get("published_source"))
    result = {
        "passed": not errors,
        "meta": meta,
        "record_count": total,
        "supplemental_record_count": supplements,
        "checks": {
            "duplicate_count": len(duplicates),
            "missing_address_count": missing_address,
            "unknown_category_count": unknown_category,
            "bad_evidence_count": bad_evidence,
            "address_coverage": pct(total - missing_address, total),
            "known_category_coverage": pct(total - unknown_category, total),
        },
        "errors": errors,
        "warnings": warnings,
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "quality.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
