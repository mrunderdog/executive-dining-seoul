from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from collections import Counter, defaultdict
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[1]
ENTITY_BRIDGES = ROOT / "sources" / "entity_bridge_overrides.json"


def t(v) -> str:
    return " ".join(str(v or "").split()).strip()


def compact(v) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", t(v).lower())


def canonical_address(v) -> str:
    s = t(v)
    if not s:
        return ""
    replacements = {
        "서울특별시": "서울", "서울시": "서울",
        "경기도": "경기", "인천광역시": "인천", "부산광역시": "부산",
        "대구광역시": "대구", "대전광역시": "대전", "광주광역시": "광주",
        "울산광역시": "울산", "세종특별자치시": "세종",
    }
    for a, b in replacements.items():
        s = s.replace(a, b)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" ,")
    # Use the road-number base as the physical-building key where possible.
    m = re.search(r"^(.+?(?:대로|로|길)\s*\d+(?:-\d+)?)\b", s)
    if m:
        return compact(m.group(1))
    # Fall back to dong + lot number.
    m = re.search(r"^(.+?[가-힣0-9]+동\s*\d+(?:-\d+)?)\b", s)
    if m:
        return compact(m.group(1))
    return compact(s)


def strict_name(v) -> str:
    """Normalized merchant name without collapsing branch/location suffixes."""
    s = t(v)
    s = re.sub(r"^(?:주식회사|유한회사|\\(주\\)|㈜)\\s*", "", s, flags=re.I)
    return compact(s)


def family_name(v) -> str:
    s = t(v)
    s = re.sub(r"^(?:주식회사|유한회사|\(주\)|㈜)\s*", "", s, flags=re.I)
    s = re.sub(r"\([^)]*(?:점|지점|호점)\)\s*$", "", s)
    suffixes = (
        r"서여의도\d*호?점$", r"서여의도점$", r"여의도아이에프씨점$", r"여의도ifc점$",
        r"여의도점$", r"일산점$", r"마포점$", r"강선점$", r"영등포점$",
        r"아이에프씨점$", r"ifc점$", r"\d+호점$",
    )
    for pat in suffixes:
        s = re.sub(pat, "", s, flags=re.I)
    return compact(s)


def _load_verified_bridges() -> dict[str, str]:
    if not ENTITY_BRIDGES.exists():
        return {}
    try:
        doc = json.loads(ENTITY_BRIDGES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for raw_name, spec in (doc.get("bridges") or {}).items():
        name = strict_name(raw_name)
        address = canonical_address((spec or {}).get("address"))
        if name and address:
            out[name] = address
    return out


def locality_key(r: dict) -> str:
    """Conservative city/county/district hint for entity matching.

    Prefer an explicit source locality hint, then a street address, then a
    concrete local-government origin. Broad origins such as 중앙정부 or
    광역단체청 are deliberately excluded.
    """
    raw = t(r.get("location_hint")) or t(r.get("address"))
    if not raw:
        origin = t(r.get("origin"))
        if re.search(r"(?:시|군|구)$", origin) and origin not in {
            "서울시청", "경기도청", "인천시청", "중앙정부",
        }:
            raw = origin
    if not raw:
        return ""
    matches = re.findall(r"([가-힣0-9]+(?:시|군|구))\b", raw)
    if not matches:
        return ""
    # In a full address the most specific locality is normally the last
    # 시/군/구 token (e.g. 인천광역시 연수구 -> 연수구).
    return compact(matches[-1])


def entity_key(r: dict) -> str:
    name = family_name(r.get("name"))
    address = canonical_address(r.get("address"))
    if name and address:
        return f"{name}||{address}"

    # When a street address is unavailable, allow a narrowly scoped fallback:
    # exact normalized merchant family + exact 시/군/구. This is useful for
    # official disclosures that publish "OO구 소재" instead of a street
    # address, while still avoiding broad cross-source name-only merges.
    locality = locality_key(r)
    if name and locality and len(name) >= 4:
        return f"{name}||locality:{locality}"

    return f"single||{compact(r.get('name'))}||{compact(r.get('origin'))}"


def _signal(r: dict) -> float:
    return max(float((r.get("executive") or {}).get("score") or 0), float((r.get("destination") or {}).get("score") or 0))


def _best_record(rows: list[dict]) -> dict:
    def quality(r):
        b = r.get("business") or {}
        known_category = 0 if "확인 필요" in t(b.get("category")) or not t(b.get("category")) else 1
        return (
            known_category,
            bool(t(r.get("address"))),
            bool(t(b.get("phone"))),
            bool(t(b.get("url"))),
            _signal(r),
            int((r.get("evidence") or {}).get("visits") or 0),
        )
    return max(rows, key=quality)


def _merge_evidence(rows: list[dict], multi_origin: bool) -> dict:
    out = {"visits": 0, "spend": 0, "people": 0, "months": 0, "evening": 0, "evening_ratio": 0, "ppc": 0,
           "date_min": "", "date_max": "", "roles": [], "purposes": [], "recent": [], "source_rows": []}
    dates_min, dates_max = [], []
    role_map = defaultdict(lambda: {"visits": 0, "people": 0, "spend": 0})
    purpose_map = Counter()
    recent = []
    source_rows = []
    for r in rows:
        e = r.get("evidence") or {}
        out["visits"] += int(e.get("visits") or 0)
        out["spend"] += int(e.get("spend") or 0)
        out["people"] += int(e.get("people") or 0)
        out["months"] = max(out["months"], int(e.get("months") or 0))
        out["evening"] += int(e.get("evening") or 0)
        if t(e.get("date_min")): dates_min.append(t(e.get("date_min")))
        if t(e.get("date_max")): dates_max.append(t(e.get("date_max")))
        prefix = t(r.get("origin"))
        for x in e.get("roles") or []:
            role = t(x.get("role"))
            if not role:
                continue
            label = f"{prefix} · {role}" if multi_origin else role
            role_map[label]["visits"] += int(x.get("visits") or 0)
            role_map[label]["people"] += int(x.get("people") or 0)
            role_map[label]["spend"] += int(x.get("spend") or 0)
        for x in e.get("purposes") or []:
            if t(x.get("text")):
                purpose_map[t(x.get("text"))] += int(x.get("count") or 0)
        for x in e.get("recent") or []:
            y = dict(x)
            if multi_origin:
                y["role"] = f"{prefix} · {t(y.get('role'))}".strip(" ·")
            recent.append(y)
        source_rows.extend(e.get("source_rows") or [])
    out["date_min"] = min(dates_min) if dates_min else ""
    out["date_max"] = max(dates_max) if dates_max else ""
    out["evening_ratio"] = round(out["evening"] / out["visits"], 3) if out["visits"] else 0
    out["ppc"] = round(out["spend"] / out["people"]) if out["people"] else 0
    out["roles"] = [{"role": k, **v} for k, v in sorted(role_map.items(), key=lambda kv: (kv[1]["visits"], kv[1]["spend"]), reverse=True)]
    out["purposes"] = [{"text": k, "count": v} for k, v in purpose_map.most_common(8)]
    out["recent"] = sorted(recent, key=lambda x: (t(x.get("date")), t(x.get("time"))), reverse=True)[:16]
    out["source_rows"] = list(dict.fromkeys(source_rows))
    return out


def _best_signal(rows: list[dict], field: str):
    candidates = [r.get(field) for r in rows if r.get(field)]
    if not candidates:
        return None
    out = deepcopy(max(candidates, key=lambda x: float(x.get("score") or 0)))
    if field == "executive":
        # Preserve specialized executive metadata across merged origins instead
        # of losing it when another cohort has a higher generic signal score.
        additive = (
            "top_official_visits", "prime_minister_visits",
            "deputy_prime_minister_visits", "minister_visits",
            "vice_minister_visits", "mayor_visits", "vice_mayor_visits",
        )
        for key in additive:
            out[key] = sum(int(x.get(key) or 0) for x in candidates)
        tier_order = {
            "": 0, "other": 0, "director_general": 1, "senior_official": 2,
            "agency_head": 3, "vice_minister": 4, "minister": 5,
            "deputy_prime_minister": 6, "prime_minister": 7,
        }
        strongest = max(
            candidates,
            key=lambda x: tier_order.get(t(x.get("top_role_tier")), 0),
        )
        if tier_order.get(t(strongest.get("top_role_tier")), 0):
            out["top_role_tier"] = t(strongest.get("top_role_tier"))
            out["top_role_label"] = t(strongest.get("top_role_label"))
    return out


def merge_global_entities(payload: dict) -> dict:
    records = list(payload.get("records") or [])

    # First index records that have a real street address. A locality-only
    # disclosure may attach to one of these only when the normalized merchant
    # family + locality resolves to exactly one strong entity. This avoids
    # unsafe name-only merges for chains with multiple branches.
    strong_index = defaultdict(set)
    strict_keys = {}
    # Address corroboration index: an addressless disclosure may inherit a
    # physical entity only when at least two independent origins already agree
    # on the exact same normalized merchant family + street address, and there
    # is no competing addressed branch for that family in the published set.
    family_address_origins = defaultdict(lambda: defaultdict(set))
    strict_address_keys = defaultdict(set)
    for idx, r in enumerate(records):
        name = family_name(r.get("name"))
        address = canonical_address(r.get("address"))
        if not name or not address:
            continue
        key = f"{name}||{address}"
        strict_keys[idx] = key
        origin = t(r.get("origin"))
        if origin:
            family_address_origins[name][key].add(origin)
        sname = strict_name(r.get("name"))
        if sname:
            strict_address_keys[sname].add(key)
        loc = locality_key(r)
        if loc:
            strong_index[(name, loc)].add(key)

    corroborated_address_index = {}
    unique_branch_address_index = {}
    unique_exact_address_index = {}
    for name, address_map in family_address_origins.items():
        if len(name) < 4 or len(address_map) != 1:
            continue
        key, origins = next(iter(address_map.items()))
        if len(origins) >= 2:
            corroborated_address_index[name] = key

    # A single addressed origin is sufficient only when the disclosure itself
    # names an explicit branch/location suffix such as "...여의도점" or
    # "...정동점", and that strict branch name resolves to exactly one address.
    for sname, keys in strict_address_keys.items():
        if len(keys) != 1:
            continue
        only_key = next(iter(keys))
        if re.search(r"(?:점|지점|호점)$", sname):
            unique_branch_address_index[sname] = only_key
        if len(sname) >= 6:
            unique_exact_address_index[sname] = only_key

    verified_bridges = _load_verified_bridges()

    groups = defaultdict(list)
    bridged_records = 0
    bridged_groups = defaultdict(int)
    for idx, r in enumerate(records):
        if idx in strict_keys:
            key = strict_keys[idx]
        else:
            name = family_name(r.get("name"))
            loc = locality_key(r)
            candidates = strong_index.get((name, loc), set()) if name and loc else set()
            if len(candidates) == 1:
                key = next(iter(candidates))
            elif not loc and name in corroborated_address_index:
                # No locality was published for this record, but independent
                # addressed origins already corroborate one and only one
                # physical branch for the merchant family.
                key = corroborated_address_index[name]
                bridged_records += 1
                bridged_groups[key] += 1
            elif not loc and strict_name(r.get("name")) in unique_branch_address_index:
                # Explicit branch name + exactly one addressed match is narrow
                # enough to bridge without collapsing generic chain names.
                key = unique_branch_address_index[strict_name(r.get("name"))]
                bridged_records += 1
                bridged_groups[key] += 1
            elif (
                not loc
                and strict_name(r.get("name")) in verified_bridges
            ):
                verified_address = verified_bridges[strict_name(r.get("name"))]
                candidate_keys = strict_address_keys.get(strict_name(r.get("name")), set())
                matches = [
                    k for k in candidate_keys
                    if k.endswith("||" + verified_address)
                ]
                if len(matches) == 1:
                    key = matches[0]
                    bridged_records += 1
                    bridged_groups[key] += 1
                else:
                    key = entity_key(r)
            elif (
                not loc
                and strict_name(r.get("name")) in unique_exact_address_index
                and len(set(r.get("institutions") or [])) >= 2
            ):
                # For long exact merchant names, repeated use by multiple
                # independent institutions provides an additional corroborating
                # signal. Bridge only when the entire published dataset contains
                # exactly one addressed physical entity for that exact name.
                key = unique_exact_address_index[strict_name(r.get("name"))]
                bridged_records += 1
                bridged_groups[key] += 1
            else:
                key = entity_key(r)
        groups[key].append(r)

    merged = []
    merged_groups = 0
    for key, rows in groups.items():
        primary = deepcopy(_best_record(rows))

        # Preserve coordinates that were published by a source dataset itself
        # (for example, the reconstructed prosecution restaurant GeoJSON).
        # Entity grouping is already address-conservative, so a source coordinate
        # may be inherited only inside the same resolved physical entity.
        source_coords = [
            r for r in rows
            if r.get("source_verified_coordinate")
            and isinstance(r.get("lat"), (int, float))
            and isinstance(r.get("lon"), (int, float))
        ]
        if source_coords:
            coord_row = max(source_coords, key=lambda r: bool(t(r.get("address"))))
            primary["lat"] = float(coord_row["lat"])
            primary["lon"] = float(coord_row["lon"])
            primary["source_verified_coordinate"] = True
            primary["source_coordinate_provenance"] = t(coord_row.get("source_coordinate_provenance"))
            primary["source_coordinate_source"] = t(coord_row.get("published_source"))

        origins = sorted({
            t(o)
            for r in rows
            for o in (r.get("origins") or ([r.get("origin")] if r.get("origin") else []))
            if t(o)
        })
        institutions = sorted({
            t(i)
            for r in rows
            for i in (r.get("institutions") or ([r.get("institution")] if r.get("institution") else []))
            if t(i)
        })
        multi = len(origins) > 1
        primary["origins"] = origins
        primary["institutions"] = institutions
        primary["source_keys"] = list(dict.fromkeys(
            f"{t(r.get('name'))}|{t(r.get('origin'))}" for r in rows if t(r.get("name")) and t(r.get("origin"))
        ))
        primary["published_sources"] = sorted({t(r.get("published_source")) for r in rows if t(r.get("published_source"))})
        primary["cohorts"] = sorted({t(r.get("cohort")) for r in rows if t(r.get("cohort"))})
        primary["entity_id"] = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        if bridged_groups.get(key):
            primary["entity_match_basis"] = "corroborated_address"
            primary["corroborated_address_bridges"] = bridged_groups[key]
        primary["evidence"] = _merge_evidence(rows, multi)
        primary["executive"] = _best_signal(rows, "executive")
        primary["destination"] = _best_signal(rows, "destination")
        primary["type"] = "both" if primary["executive"] and primary["destination"] else "executive" if primary["executive"] else "destination"

        by_origin = []
        for origin in origins:
            rr = [r for r in rows if t(r.get("origin")) == origin]
            by_origin.append({
                "origin": origin,
                "visits": sum(int((r.get("evidence") or {}).get("visits") or 0) for r in rr),
                "spend": sum(int((r.get("evidence") or {}).get("spend") or 0) for r in rr),
                "records": len(rr),
            })
        cohort_count = len(primary["cohorts"])
        institution_count = len(institutions)
        source_count = len(origins)
        total_visits = int(primary["evidence"].get("visits") or 0)
        is_cross = institution_count >= 2
        consensus_score = 0.0
        if is_cross:
            consensus_score = round(100 * (
                .35 * min(math.log1p(institution_count) / math.log1p(4), 1)
                + .20 * min(math.log1p(source_count) / math.log1p(4), 1)
                + .25 * min(math.log1p(total_visits) / math.log1p(20), 1)
                + .20 * min(cohort_count / 3, 1)
            ), 1)
        primary["cross_institution"] = {
            "source_count": source_count,
            "institution_count": institution_count,
            "cohort_count": cohort_count,
            "origins": origins,
            "institutions": institutions,
            "cohorts": primary["cohorts"],
            "by_origin": by_origin,
            "visits": total_visits,
            "score": consensus_score,
            "is_cross": is_cross,
        }
        if is_cross:
            merged_groups += 1
            primary["why"] = (
                f"{institution_count}개 기관·{source_count}개 출처에서 독립적으로 선택된 동일 식당으로 확인됩니다. "
                f"합산 {total_visits}회 방문 기록이 있으며, 기관 간 교차 선택 신호입니다."
            )
        merged.append(primary)

    merged.sort(key=lambda r: (_signal(r), int((r.get("evidence") or {}).get("visits") or 0)), reverse=True)
    out = dict(payload)
    out["records"] = merged
    out["origins"] = sorted({o for r in merged for o in (r.get("origins") or [r.get("origin")]) if o})
    stats = dict(out.get("stats") or {})
    stats["pre_entity_total"] = len(records)
    stats["total"] = len(merged)
    stats["entity_merges"] = len(records) - len(merged)
    stats["cross_institution"] = sum(bool((r.get("cross_institution") or {}).get("is_cross")) for r in merged)
    stats["destination"] = sum(bool(r.get("destination")) for r in merged)
    stats["executive"] = sum(bool(r.get("executive")) for r in merged)
    stats["both"] = sum(bool(r.get("destination")) and bool(r.get("executive")) for r in merged)
    out["stats"] = stats
    meta = dict(out.get("meta") or {})
    meta["entity_model"] = "global_restaurant_entity_v3"
    meta["entity_merge_groups"] = merged_groups
    meta["corroborated_address_bridges"] = bridged_records
    out["meta"] = meta
    return out
