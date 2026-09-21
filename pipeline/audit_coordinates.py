#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from coordinate_selection import coordinate_candidates, geocode_address_key, select_coordinate
from data_io import load_payload
from extra_published import merge_extra_published
from global_entities import canonical_address, merge_global_entities
from published_sources import merge_published_sources

ROOT = Path(__file__).resolve().parents[1]
GEO_CACHE = ROOT / "data" / "geocode_cache.json"
REPORTS = ROOT / "reports"


def load_geo() -> dict:
    obj = json.loads(GEO_CACHE.read_text(encoding="utf-8"))
    return obj.get("records", obj)


def main():
    payload = merge_global_entities(
        merge_extra_published(
            merge_published_sources(load_payload())
        )
    )
    records = payload.get("records") or []
    geo = load_geo()

    issues = []
    selected = 0
    address_records = 0
    prevented = 0
    missing_safe = 0

    for r in records:
        target = canonical_address(r.get("address"))
        if target:
            address_records += 1

        candidates = coordinate_candidates(r, geo)
        old_key = candidates[0][0] if candidates else None
        old_row = candidates[0][1] if candidates else None
        new_key, new_row, meta = select_coordinate(r, geo)
        if new_row:
            selected += 1

        old_mismatch = bool(
            target and old_row and geocode_address_key(old_row) != target
        )
        changed = bool(old_key and new_key and old_key != new_key)
        dropped = bool(old_key and not new_key and target)
        if old_mismatch or changed or dropped:
            prevented += int(old_mismatch)
            missing_safe += int(dropped)
            issues.append({
                "name": r.get("name"),
                "address": r.get("address"),
                "origins": r.get("origins") or [r.get("origin")],
                "old_key": old_key,
                "old_match_mode": (old_row or {}).get("match_mode"),
                "old_query": (old_row or {}).get("query"),
                "old_display_name": (old_row or {}).get("display_name"),
                "old_lat": (old_row or {}).get("lat"),
                "old_lon": (old_row or {}).get("lon"),
                "new_key": new_key,
                "new_match_mode": (new_row or {}).get("match_mode"),
                "new_query": (new_row or {}).get("query"),
                "new_display_name": (new_row or {}).get("display_name"),
                "new_lat": (new_row or {}).get("lat"),
                "new_lon": (new_row or {}).get("lon"),
                "old_address_mismatch": old_mismatch,
                "changed_selection": changed,
                "safe_coordinate_missing": dropped,
                "rejected_candidates": meta.get("rejected_candidates") or [],
            })

    doc = {
        "records": len(records),
        "address_records": address_records,
        "safe_coordinates": selected,
        "unsafe_old_selections_prevented": prevented,
        "safe_coordinate_missing": missing_safe,
        "issue_count": len(issues),
        "issues": issues,
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "coordinate-audit.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md = [
        "# Coordinate audit",
        "",
        f"- Published entities: **{len(records)}**",
        f"- Entities with published address: **{address_records}**",
        f"- Safe static coordinates selected: **{selected}**",
        f"- Unsafe legacy selections prevented: **{prevented}**",
        f"- Addressed entities now left without a safe coordinate: **{missing_safe}**",
        f"- Changed/dropped selections: **{len(issues)}**",
        "",
        "| Restaurant | Address | Old key | New key | Old mismatch | Safe missing |",
        "|---|---|---|---|---|---|",
    ]
    for x in issues[:150]:
        md.append(
            f"| {str(x['name']).replace('|','/')} | {str(x['address']).replace('|','/')} | "
            f"{str(x['old_key'] or '-').replace('|','/')} | {str(x['new_key'] or '-').replace('|','/')} | "
            f"{x['old_address_mismatch']} | {x['safe_coordinate_missing']} |"
        )
    (REPORTS / "coordinate-audit.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in doc.items() if k != "issues"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
