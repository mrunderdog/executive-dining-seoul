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

    # No published address: address-mode geocodes are safer than name-only POIs.
    candidates.sort(key=lambda item: (
        0 if item[1].get("match_mode") == "address" else 1,
        -(float(item[1].get("score") or 0)),
    ))
    return candidates[0][0], candidates[0][1], meta
