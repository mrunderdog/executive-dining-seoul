from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"

# Conservative publication gate: only clearly repeated chair/vice-chair choices are
# promoted from staged raw data into the public map. This avoids flooding the map
# with one-off lunches while the capital-area adapters are still being expanded.
SOURCE_SPECS = {
    "goyang": {
        "origin": "고양시",
        "region": "경기",
        "jurisdiction": "고양특례시",
        "institution": "고양특례시의회",
        "min_visits": 4,
        "min_months": 3,
        "min_score": 55.0,
        "max_records": 30,
        "home_tokens": ("고양",),
    }
}

CATEGORY_RULES = [
    (("참치",), "일식·참치"),
    (("스시", "초밥"), "일식·스시/초밥"),
    (("횟집", "회집", "세꼬시", "수산", "사시미", "어촌"), "회·해산물"),
    (("복어", "복집"), "복어"),
    (("아구", "동태", "코다리", "갈치", "낙지", "쭈꾸미", "꼼장어", "생선"), "해물·생선"),
    (("한우", "갈비", "숯불", "고기", "삼겹", "곱창", "막창", "축산", "오리", "돈판"), "고기·구이"),
    (("장어",), "장어"),
    (("삼계탕", "추어탕", "순대", "설렁탕", "곰탕", "감자탕", "해장국", "국밥", "찌개", "전골"), "국물·탕"),
    (("면옥", "냉면", "막국수", "칼국수", "소바", "국수", "메밀"), "면·국수"),
    (("족발",), "족발"),
    (("보쌈",), "보쌈"),
    (("반점", "중화", "짜장", "짬뽕", "샤오롱", "하인선생", "남궁"), "중식"),
    (("치킨", "통닭", "비비큐"), "치킨"),
    (("샤브",), "샤브샤브"),
    (("파스타", "비스트로", "레스토랑"), "양식"),
    (("분식", "김밥"), "분식"),
]


def _txt(v) -> str:
    return " ".join(str(v or "").split()).strip()


def _role_bucket(role: str) -> str | None:
    s = re.sub(r"\s+", "", _txt(role))
    if s == "의장":
        return "의장"
    if s == "부의장":
        return "부의장"
    return None


def _category(name: str) -> str:
    for words, label in CATEGORY_RULES:
        if any(w in name for w in words):
            return f"{label} (상호명 기반 추정)"
    return "업종 확인 필요"


def _most_common(values: list[str]) -> str:
    vals = [_txt(x) for x in values if _txt(x)]
    return Counter(vals).most_common(1)[0][0] if vals else ""


def _is_evening(value: str) -> bool:
    m = re.match(r"\s*(\d{1,2})(?::|시)", _txt(value))
    return bool(m and int(m.group(1)) >= 17)


def _is_outside_home(address: str, home_tokens: tuple[str, ...]) -> bool | None:
    a = _txt(address)
    if not a:
        return None
    return not any(token in a for token in home_tokens)


def _destination_score(visits: int, roles: int, months: int, evening_ratio: float, outside_ratio: float) -> float:
    # Mirrors the published Seoul Destination signal shape, but uses the source's
    # own observed maximum implicitly capped at meaningful repeated-use levels.
    distance = min(max(outside_ratio, 0.0), 1.0)
    visit_norm = min(math.log1p(visits) / math.log1p(10), 1.0)
    exec_norm = visit_norm  # all staged rows here are chair/vice-chair rows
    role_norm = min(roles / 4, 1.0)
    month_norm = min(months / 5, 1.0)
    score = 100 * (
        0.25 * distance
        + 0.25 * visit_norm
        + 0.20 * exec_norm
        + 0.15 * role_norm
        + 0.10 * month_norm
        + 0.05 * evening_ratio
    )
    return round(score, 1)


def _load_source(source: str) -> tuple[dict, dict] | None:
    raw_path = RAW_DIR / f"{source}_expense.json"
    cand_path = REPORTS / f"{source}-executive-candidates.json"
    if not raw_path.exists() or not cand_path.exists():
        return None
    return (
        json.loads(raw_path.read_text(encoding="utf-8")),
        json.loads(cand_path.read_text(encoding="utf-8")),
    )


def _build_source_records(source: str, spec: dict) -> list[dict]:
    loaded = _load_source(source)
    if not loaded:
        return []
    raw, candidates_doc = loaded
    candidates = candidates_doc.get("candidates", [])
    selected = [
        c for c in candidates
        if int(c.get("visits") or 0) >= spec["min_visits"]
        and int(c.get("months") or 0) >= spec["min_months"]
        and float(c.get("score") or 0) >= spec["min_score"]
    ][: spec["max_records"]]
    selected_names = {c["merchant"] for c in selected}

    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in raw.get("rows", []):
        name = _txt(r.get("merchant"))
        if name not in selected_names:
            continue
        if r.get("date_quality") != "in_period":
            continue
        if not _role_bucket(r.get("role")):
            continue
        grouped[name].append(r)

    out: list[dict] = []
    for rank, c in enumerate(selected, start=1):
        name = c["merchant"]
        rows = grouped.get(name, [])
        if not rows:
            continue
        rows = sorted(rows, key=lambda x: (x.get("used_date") or "", x.get("used_time") or ""))
        visits = len(rows)
        spend = sum(int(r.get("amount") or 0) for r in rows)
        people = sum(int(r.get("people") or 0) for r in rows)
        months_set = sorted({(r.get("used_date") or "")[:7] for r in rows if re.match(r"20\d{2}-\d{2}", r.get("used_date") or "")})
        evening = sum(_is_evening(r.get("used_time") or "") for r in rows)
        evening_ratio = round(evening / visits, 3) if visits else 0
        address = _most_common([r.get("address") or "" for r in rows])

        role_map: dict[str, dict] = defaultdict(lambda: {"visits": 0, "people": 0, "spend": 0})
        for r in rows:
            role = _role_bucket(r.get("role")) or _txt(r.get("role")) or "직책 미상"
            role_map[role]["visits"] += 1
            role_map[role]["people"] += int(r.get("people") or 0)
            role_map[role]["spend"] += int(r.get("amount") or 0)
        roles = [
            {"role": role, **vals}
            for role, vals in sorted(role_map.items(), key=lambda kv: (kv[1]["visits"], kv[1]["spend"]), reverse=True)
        ]

        purposes_count = Counter(_txt(r.get("purpose")) for r in rows if _txt(r.get("purpose")))
        purposes = [{"text": text, "count": count} for text, count in purposes_count.most_common(5)]
        recent = [
            {
                "date": _txt(r.get("used_date")),
                "time": _txt(r.get("used_time")),
                "role": _role_bucket(r.get("role")) or _txt(r.get("role")),
                "people": int(r.get("people") or 0),
                "amount": int(r.get("amount") or 0),
                "purpose": _txt(r.get("purpose")),
                "source": _txt(r.get("source_post_url")),
            }
            for r in reversed(rows[-8:])
        ]

        outside_flags = [_is_outside_home(r.get("address") or "", spec["home_tokens"]) for r in rows]
        outside_known = [x for x in outside_flags if x is not None]
        outside_count = sum(1 for x in outside_known if x)
        outside_ratio = round(outside_count / len(outside_known), 3) if outside_known else 0.0
        has_destination = outside_count >= 2 and outside_ratio >= 0.5
        destination = None
        if has_destination:
            destination = {
                "rank": rank,
                "score": _destination_score(visits, len(roles), len(months_set), evening_ratio, outside_ratio),
                "events": visits,
                "exec_events": visits,
                "roles": len(roles),
                "months": len(months_set),
                "evening_ratio": evening_ratio,
                "outside_ratio": outside_ratio,
                "source": source,
            }

        executive = {
            "rank": rank,
            "score": round(float(c.get("score") or 0), 1),
            "exec_events": visits,
            "roles": len(roles),
            "months": len(months_set),
            "evening_ratio": evening_ratio,
            "source": source,
        }
        typ = "both" if destination else "executive"
        role_label = "·".join(r["role"] for r in roles[:2]) if roles else "의장단"
        why = f"{spec['institution']} {role_label} 공개 업무추진비에서 {visits}회 반복 선택, {len(months_set)}개월 지속"
        if evening_ratio >= 0.5:
            why += f", 저녁 사용 {round(evening_ratio*100)}%"
        if has_destination:
            why += f", 고양시 밖 주소 사용 비중 {round(outside_ratio*100)}%"
        why += "이 확인됩니다."

        out.append({
            "name": name,
            "origin": spec["origin"],
            "region": spec["region"],
            "jurisdiction": spec["jurisdiction"],
            "institution": spec["institution"],
            "type": typ,
            "destination": destination,
            "executive": executive,
            "address": address,
            "search_query": " ".join(x for x in (name, address or spec["jurisdiction"]) if x),
            "business": {
                "display": name,
                "category": _category(name),
                "phone": "",
                "status": "공개 원자료상 업소명 확인",
                "rating": "",
                "note": f"{spec['institution']} 공개 업무추진비 원자료 기반. 현재 영업 여부/지점은 별도 확인 필요.",
                "url": "",
            },
            "evidence": {
                "visits": visits,
                "spend": spend,
                "people": people,
                "months": len(months_set),
                "evening": evening,
                "evening_ratio": evening_ratio,
                "ppc": round(spend / people) if people else 0,
                "date_min": rows[0].get("used_date") or "",
                "date_max": rows[-1].get("used_date") or "",
                "roles": roles,
                "purposes": purposes,
                "recent": recent,
                "source_rows": [r.get("row_id") for r in rows if r.get("row_id")],
            },
            "why": why,
            "published_source": source,
        })
    return out


def merge_published_sources(payload: dict) -> dict:
    base = list(payload.get("records", []))
    seen = {(str(r.get("name", "")).strip(), str(r.get("origin", "")).strip()) for r in base}
    added: list[dict] = []
    for source, spec in SOURCE_SPECS.items():
        for r in _build_source_records(source, spec):
            k = (r["name"], r["origin"])
            if k in seen:
                continue
            seen.add(k)
            added.append(r)
    records = base + added
    payload = dict(payload)
    payload["records"] = records
    payload["origins"] = sorted({str(r.get("origin", "")).strip() for r in records if str(r.get("origin", "")).strip()})
    payload["stats"] = {
        "total": len(records),
        "destination": sum(bool(r.get("destination")) for r in records),
        "executive": sum(bool(r.get("executive")) for r in records),
        "both": sum(bool(r.get("destination")) and bool(r.get("executive")) for r in records),
        "supplemental": len(added),
    }
    meta = dict(payload.get("meta") or {})
    meta["published_supplements"] = {source: sum(1 for r in added if r.get("published_source") == source) for source in SOURCE_SPECS}
    meta["scope"] = "서울·경기·인천 수도권 기초의회 (지원 source부터 단계적 자동 게시)"
    payload["meta"] = meta
    return payload
