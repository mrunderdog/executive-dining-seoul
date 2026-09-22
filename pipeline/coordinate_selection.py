from __future__ import annotations

from global_entities import canonical_address, t


def has_coords(row: dict) -> bool:
    return isinstance(row.get("lat"), (int, float)) and isinstance(row.get("lon"), (int, float))


def geocode_address_key(row: dict) -> str:
    # Prefer the exact query that produced the cached geocode. Address-mode
    # geocoders may insert dong/neighborhood text into display_name even when
    # the road-address target is the same physical place.
    for field in ("query", "display_name"):
        value = t(row.get(field))
        if not value:
            continue
        key = canonical_address(value)
        if key:
            return key
    return ""


def coordinate_candidates(record: dict, geo: dict) -> list[tuple[str, dict]]:
    keys = []
    primary = f"{record.get('name', '')}|{record.get('origin', '')}"
    if primary.strip("|"):
        keys.append(primary)
    keys.extend(record.get("source_keys") or [])
    out = []
    seen = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        row = geo.get(key) or {}
        if has_coords(row):
            out.append((key, row))
    return out


UNSAFE_NAME_ADDR_TYPES = {
    "locality", "region", "country", "postal", "neighborhood", "district", "admin",
}


def unsafe_name_geocode(row: dict) -> bool:
    """Reject name-only geocodes that resolved to a geographic place, not a venue."""
    if t(row.get("match_mode")).lower() != "name":
        return False
    addr_type = t(row.get("addr_type")).lower()
    return any(token in addr_type for token in UNSAFE_NAME_ADDR_TYPES)


def select_coordinate(record: dict, geo: dict) -> tuple[str | None, dict | None, dict]:
    """Choose a coordinate conservatively.

    If the restaurant has a published street address, never use a name-only
    geocode from another merged source. Prefer candidates whose normalized
    geocoder address matches the restaurant's canonical street address.
    """
    candidates = coordinate_candidates(record, geo)
    target = canonical_address(record.get("address"))
    meta = {
        "target_address_key": target,
        "candidate_count": len(candidates),
        "rejected_candidates": [],
    }
    if not candidates:
        return None, None, meta

    if target:
        matched = []
        for key, row in candidates:
            gkey = geocode_address_key(row)
            if gkey == target:
                matched.append((key, row))
            else:
                meta["rejected_candidates"].append({
                    "key": key,
                    "match_mode": row.get("match_mode"),
                    "query": row.get("query"),
                    "display_name": row.get("display_name"),
                    "lat": row.get("lat"),
                    "lon": row.get("lon"),
                    "reason": "address_mismatch",
                })
        if matched:
            matched.sort(key=lambda item: (
                0 if item[1].get("match_mode") == "address" else 1,
                -(float(item[1].get("score") or 0)),
            ))
            return matched[0][0], matched[0][1], meta
        return None, None, meta

    # National-level records with no published/verified address are too
    # ambiguous for name-only geocoding. A generic restaurant name such as
    # "낙원" can resolve to an unrelated POI anywhere in Korea and create a
    # convincing but false marker. Keep the record/list evidence, but suppress
    # the map coordinate until a street address is verified.
    if t(record.get("jurisdiction")) in {"대한민국", "전국"} or t(record.get("cohort")) in {"central_executive", "national_legislator"}:
        for key, row in candidates:
            meta["rejected_candidates"].append({
                "key": key,
                "match_mode": row.get("match_mode"),
                "addr_type": row.get("addr_type"),
                "query": row.get("query"),
                "display_name": row.get("display_name"),
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "reason": "national_record_without_verified_address",
            })
        return None, None, meta

    # No published address: never accept a name-only hit that is actually a
    # locality/region/etc. ArcGIS can score a place name such as "운산 대한민국"
    # at 100 even though it is not a restaurant.
    safe = []
    for key, row in candidates:
        if unsafe_name_geocode(row):
            meta["rejected_candidates"].append({
                "key": key,
                "match_mode": row.get("match_mode"),
                "addr_type": row.get("addr_type"),
                "query": row.get("query"),
                "display_name": row.get("display_name"),
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "reason": "name_resolved_to_geographic_locality",
            })
            continue
        safe.append((key, row))

    if not safe:
        return None, None, meta

    # Address-mode geocodes are safer than name-only POIs.
    safe.sort(key=lambda item: (
        0 if item[1].get("match_mode") == "address" else 1,
        -(float(item[1].get("score") or 0)),
    ))
    return safe[0][0], safe[0][1], meta
