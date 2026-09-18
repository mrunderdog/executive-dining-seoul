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
    from global_entities import merge_global_entities
    payload = merge_global_entities(merge_extra_published(merge_published_sources(load_payload())))
    meta = payload.get("meta", {})
    records = payload.get("records", [])
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(records, list) or not records:
        errors.append("records must be a non-empty list")

    keys_seen = Counter()
    entity_ids = Counter()
    cross_entities = 0
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
        if r.get("entity_id"):
            entity_ids[str(r.get("entity_id"))] += 1
        if (r.get("cross_institution") or {}).get("is_cross"):
            cross_entities += 1

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
    duplicate_entity_ids = [eid for eid, count in entity_ids.items() if count > 1]
    if duplicate_entity_ids:
        errors.append("duplicate global entity_id values: " + "; ".join(duplicate_entity_ids[:20]))

    total = len(records)
    if total:
        if pct(missing_address, total) > 0.65:
            warnings.append(f"address coverage is low: {total-missing_address}/{total}")
        if pct(unknown_category, total) > 0.60:
            warnings.append(f"category coverage is low: {total-unknown_category}/{total}")

    # National-legislator publication is governed by a dedicated entity/map QA report.
    legislator_candidates = REPORTS / "national-legislator-candidates.json"
    legislator_qa = REPORTS / "national-legislator-map-qa.json"
    legislator_records = [r for r in records if r.get("published_source") == "national_legislator_2024"]
    if legislator_candidates.exists():
        if not legislator_qa.exists():
            errors.append("national legislator candidates exist but map QA report is missing")
        else:
            try:
                qdoc = json.loads(legislator_qa.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"national legislator QA report is unreadable: {exc}")
                qdoc = {}
            if qdoc and not qdoc.get("passed"):
                errors.append("national legislator map QA gate did not pass")
            approved = qdoc.get("approved") or []
            expected = min(80, len(approved))
            if len(legislator_records) != expected:
                errors.append(
                    f"national legislator published count mismatch: records={len(legislator_records)}, approved={expected}"
                )
            approved_names = {str(x.get("merchant", "")).strip() for x in approved[:80]}
            leaked = [str(r.get("name", "")).strip() for r in legislator_records if str(r.get("name", "")).strip() not in approved_names]
            if leaked:
                errors.append("non-QA legislator records leaked into publication: " + "; ".join(leaked[:20]))

            geo_path = ROOT / "data" / "geocode_cache.json"
            if geo_path.exists():
                try:
                    geo_obj = json.loads(geo_path.read_text(encoding="utf-8"))
                    geo_records = geo_obj.get("records", geo_obj if isinstance(geo_obj, dict) else {})
                except (OSError, json.JSONDecodeError):
                    geo_records = {}
                missing_leg_coords = []
                for r in legislator_records:
                    key = f"{r.get('name','')}|{r.get('origin','')}"
                    g = geo_records.get(key) or {}
                    if not isinstance(g.get("lat"), (int, float)) or not isinstance(g.get("lon"), (int, float)):
                        missing_leg_coords.append(str(r.get("name", "")))
                if missing_leg_coords:
                    errors.append(
                        "QA-approved legislator records missing static coordinates: "
                        + "; ".join(missing_leg_coords[:20])
                    )

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
            "cross_institution_entity_count": cross_entities,
            "duplicate_entity_id_count": len(duplicate_entity_ids),
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
