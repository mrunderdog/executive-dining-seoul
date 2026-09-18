from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from copy import deepcopy


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


def locality_key(r: dict) -> str:
    """Conservative city/county/district hint for no-address entity matching.

    Exact street addresses remain the primary key. This fallback is only used
    when the source itself gives a locality (for example "인천 연수구 소재")
    or the origin is a concrete 시/군/구. Broad origins such as 중앙정부,
    서울시청, 경기도청 are deliberately excluded.
    """
    raw = t(r.get("location_hint"))
    if not raw:
        origin = t(r.get("origin"))
        if re.search(r"(?:시|군|구)$", origin) and origin not in {
            "서울시청", "경기도청", "인천시청", "중앙정부",
        }:
            raw = origin
    if not raw:
        return ""
    m = re.search(r"([가-힣0-9]+(?:시|군|구))\b", raw)
    if not m:
        return ""
    return compact(m.group(1))


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
    return deepcopy(max(candidates, key=lambda x: float(x.get("score") or 0)))


def merge_global_entities(payload: dict) -> dict:
    records = list(payload.get("records") or [])
    groups = defaultdict(list)
    for r in records:
        groups[entity_key(r)].append(r)

    merged = []
    merged_groups = 0
    for key, rows in groups.items():
        primary = deepcopy(_best_record(rows))
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
    meta["entity_model"] = "global_restaurant_entity_v2"
    meta["entity_merge_groups"] = merged_groups
    out["meta"] = meta
    return out
