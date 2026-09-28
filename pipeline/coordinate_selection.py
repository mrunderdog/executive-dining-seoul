from __future__ import annotations

from global_entities import canonical_address, t
import re


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

        # A manually verified HIGH-confidence business enrichment may add a
        # street address after the original name-only POI coordinate was cached.
        # Preserve that already accepted marker only when the cached POI name
        # exactly matches the verified business/name; never use this for generic
        # or ambiguous name hits.
        b = record.get("business") or {}
        if t(b.get("verification_confidence")).upper() == "HIGH":
            wanted = {
                _norm_business_name(record.get("name")),
                _norm_business_name(b.get("display")),
            }
            wanted.discard("")
            exact_name = []
            for key, row in candidates:
                if t(row.get("match_mode")).lower() != "name" or unsafe_name_geocode(row):
                    continue
                got = _norm_business_name(row.get("result_name"))
                if got and got in wanted:
                    exact_name.append((key, row))
            if exact_name:
                exact_name.sort(key=lambda item: -(float(item[1].get("score") or 0)))
                meta["verified_name_coordinate_fallback"] = exact_name[0][0]
                return exact_name[0][0], exact_name[0][1], meta
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


def _norm_business_name(v: str) -> str:
    s = t(v).lower()
    s = re.sub(r"^(?:주식회사|유한회사|\(주\)|㈜)\s*", "", s)
    return re.sub(r"[^0-9a-z가-힣]", "", s)


def _nominatim_street_address(display_name: str) -> str:
    """Convert a Nominatim POI display name to a compact Korean street address."""
    parts = [t(x) for x in str(display_name or "").split(",") if t(x)]
    if not parts:
        return ""
    parts = [x for x in parts if x != "대한민국" and not re.fullmatch(r"\d{5}", x)]
    road_idx = next((i for i, x in enumerate(parts) if re.search(r"(?:대로|로|길)(?:\d+번길)?$", x)), None)
    if road_idx is None:
        return ""
    road = parts[road_idx]
    number = parts[road_idx - 1] if road_idx > 0 and re.fullmatch(r"\d+(?:-\d+)?", parts[road_idx - 1]) else ""
    provinces = [x for x in parts[road_idx + 1:] if re.search(r"(?:특별시|광역시|특별자치시|특별자치도|도)$", x)]
    cities = [x for x in parts[road_idx + 1:] if re.search(r"(?:시)$", x) and x not in provinces]
    districts = [x for x in parts[road_idx + 1:] if re.search(r"(?:구|군)$", x)]
    admin = []
    for bucket in (provinces[-1:] if provinces else [], cities[-1:] if cities else [], districts[-1:] if districts else []):
        for x in bucket:
            if x not in admin:
                admin.append(x)
    if not admin:
        return ""
    street = f"{road} {number}".strip()
    return " ".join(admin + [street]).strip()


def safe_geocoder_address(record: dict, geo: dict) -> tuple[str, str]:
    """Return a conservative address inferred from an exact-name Nominatim POI hit.

    This never overwrites a published address. National records require an exact
    normalized business-name match; local records may allow a narrow prefix match
    when the resolved address contains the record's locality.
    """
    if t(record.get("address")):
        return "", ""
    wanted = {
        _norm_business_name(record.get("name")),
        _norm_business_name((record.get("business") or {}).get("display")),
    }
    wanted.discard("")
    if not wanted:
        return "", ""
    national = t(record.get("jurisdiction")) in {"대한민국", "전국"} or t(record.get("cohort")) in {"central_executive", "national_legislator"}
    locality = t(record.get("origin")) if not national else ""
    for key, row in coordinate_candidates(record, geo):
        if t(row.get("source")).lower() != "nominatim" or t(row.get("match_mode")).lower() != "name":
            continue
        got = _norm_business_name(row.get("result_name"))
        if not got:
            continue
        exact = got in wanted
        narrow_local = (
            not national
            and any((w in got or got in w) and min(len(w), len(got)) >= 4 for w in wanted)
            and (not locality or locality in t(row.get("display_name")))
        )
        if not exact and not narrow_local:
            continue
        address = _nominatim_street_address(row.get("display_name"))
        if address:
            return address, key
    return "", ""
