from __future__ import annotations

import json
from pathlib import Path

from published_sources import _category, ENTITY_OVERRIDES

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def t(v) -> str:
    return " ".join(str(v or "").split()).strip()


CENTRAL_ROLE_TIER_ORDER = {
    "other": 0,
    "director_general": 1,
    "senior_official": 2,
    "agency_head": 3,
    "vice_minister": 4,
    "minister": 5,
    "deputy_prime_minister": 6,
    "prime_minister": 7,
}
CENTRAL_ROLE_TIER_LABEL = {
    "other": "기타 공개 직위",
    "director_general": "국장급",
    "senior_official": "실장급",
    "agency_head": "기관장·본부장급",
    "vice_minister": "차관급",
    "minister": "장관급",
    "deputy_prime_minister": "부총리급",
    "prime_minister": "국무총리급",
}


def _central_role_tier(role: str) -> str:
    s = t(role)
    if "국무총리" in s or s == "총리":
        return "prime_minister"
    if "부총리" in s:
        return "deputy_prime_minister"
    if "차관" in s:
        return "vice_minister"
    if "장관" in s:
        return "minister"
    if any(x in s for x in ("처장", "청장", "본부장")):
        return "agency_head"
    if "실장" in s:
        return "senior_official"
    if "국장" in s:
        return "director_general"
    return "other"


def _central_tier_summary(candidate: dict) -> dict:
    counts = {k: 0 for k in CENTRAL_ROLE_TIER_ORDER}
    for row in candidate.get("role_stats") or []:
        tier = _central_role_tier(row.get("role"))
        counts[tier] += int(row.get("visits") or 0)
    top = max(counts, key=lambda k: CENTRAL_ROLE_TIER_ORDER[k]) if any(counts.values()) else "other"
    return {
        "top_role_tier": top,
        "top_role_label": CENTRAL_ROLE_TIER_LABEL[top],
        "top_official_visits": sum(counts[k] for k in ("prime_minister", "deputy_prime_minister", "minister", "vice_minister")),
        "prime_minister_visits": counts["prime_minister"],
        "deputy_prime_minister_visits": counts["deputy_prime_minister"],
        "minister_visits": counts["minister"],
        "vice_minister_visits": counts["vice_minister"],
    }


def _legislator_candidate_doc() -> dict:
    p = REPORTS / "national-legislator-candidates.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _legislator_qa_doc() -> dict:
    p = REPORTS / "national-legislator-map-qa.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def central_records(max_records: int = 120) -> list[dict]:
    p = REPORTS / "central-executive-candidates.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for rank, c in enumerate((d.get("candidates") or [])[:max_records], 1):
        name = t(c.get("merchant"))
        override = ENTITY_OVERRIDES.get(name, {})
        address = t(c.get("address")) or t(override.get("address"))
        display_name = t(override.get("display")) or name
        if not name:
            continue
        inst = c.get("institutions") or []
        visits = int(c.get("visits") or 0)
        months = int(c.get("months") or 0)
        score = float(c.get("score") or 0)
        spend = int(c.get("spend") or 0)
        inferred_tiers = _central_tier_summary(c)
        top_role_tier = t(c.get("top_role_tier")) or inferred_tiers["top_role_tier"]
        top_role_label = t(c.get("top_role_label")) or inferred_tiers["top_role_label"]
        top_official_visits = int(c.get("top_official_visits") or inferred_tiers["top_official_visits"])
        prime_minister_visits = int(c.get("prime_minister_visits") or inferred_tiers["prime_minister_visits"])
        deputy_prime_minister_visits = int(c.get("deputy_prime_minister_visits") or inferred_tiers["deputy_prime_minister_visits"])
        minister_visits = int(c.get("minister_visits") or inferred_tiers["minister_visits"])
        vice_minister_visits = int(c.get("vice_minister_visits") or inferred_tiers["vice_minister_visits"])
        roles = [
            {"role": t(x.get("role")), "visits": int(x.get("visits") or 0), "people": 0, "spend": 0}
            for x in (c.get("role_stats") or []) if t(x.get("role"))
        ]
        recent = [
            {
                "date": t(x.get("date")),
                "time": t(x.get("time")),
                "role": f"{t(x.get('institution'))} {t(x.get('role'))}".strip(),
                "people": int(x.get("people") or 0),
                "amount": int(x.get("amount") or 0),
                "purpose": t(x.get("purpose")),
                "source": t(x.get("source")),
            }
            for x in (c.get("recent") or [])
        ]
        out.append({
            "name": name,
            "origin": "중앙정부",
            "region": "전국",
            "jurisdiction": "대한민국",
            "institution": " · ".join(inst[:4]) or "중앙행정기관",
            "institutions": inst,
            "type": "executive",
            "destination": None,
            "executive": {
                "rank": rank,
                "score": round(score, 1),
                "exec_events": visits,
                "roles": int(c.get("role_count") or 0),
                "months": months,
                "evening_ratio": 0,
                "source": "central_executive",
                "top_role_tier": top_role_tier,
                "top_role_label": top_role_label,
                "top_official_visits": top_official_visits,
                "prime_minister_visits": prime_minister_visits,
                "deputy_prime_minister_visits": deputy_prime_minister_visits,
                "minister_visits": minister_visits,
                "vice_minister_visits": vice_minister_visits,
            },
            "address": address,
            "search_query": f"{display_name} {address or '대한민국'}",
            "business": {
                "display": display_name,
                "category": _category(name),
                "phone": t(override.get("phone")),
                "status": "중앙부처 공식 업무추진비 원자료 + 업체정보 보강" if override else "중앙부처 공식 업무추진비 원자료상 사용처",
                "rating": "",
                "note": (
                    "중앙행정기관이 공개한 장·차관/고위직 업무추진비 원자료 기반. 주소·전화·업종은 확인 가능한 업체만 별도 보강."
                    if override else
                    "중앙행정기관이 공개한 장·차관/고위직 업무추진비의 파싱 가능한 XLS/XLSX/CSV 원자료 기반."
                ),
                "url": t(override.get("url")),
                "verified_at": t(override.get("verified_at")),
                "verification_confidence": t(override.get("confidence")),
            },
            "evidence": {
                "visits": visits,
                "spend": spend,
                "people": 0,
                "months": months,
                "evening": 0,
                "evening_ratio": 0,
                "ppc": 0,
                "date_min": t(c.get("date_min")),
                "date_max": t(c.get("date_max")),
                "roles": roles,
                "purposes": c.get("purpose_stats") or [],
                "recent": recent,
                "source_rows": [],
            },
            "why": (
                f"중앙행정기관 공식 업무추진비에서 {visits}회, {len(inst)}개 기관/공개 직위군에 걸쳐 확인된 사용처입니다."
                + (f" 이 중 총리·장·차관급 공개 직위 사용 {top_official_visits}회가 확인됩니다." if top_official_visits else "")
            ),
            "published_source": "central_executive",
            "cohort": "central_executive",
        })
    return out


def justice_records(max_records: int = 120) -> list[dict]:
    p = REPORTS / "justice-leadership-candidates.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for rank, c in enumerate((d.get("candidates") or [])[:max_records], 1):
        name = t(c.get("merchant"))
        if not name:
            continue
        override = ENTITY_OVERRIDES.get(name, {})
        address = t(c.get("address")) or t(override.get("address"))
        display_name = t(override.get("display")) or name
        inst = c.get("institutions") or []
        visits = int(c.get("visits") or 0)
        months = int(c.get("months") or 0)
        spend = int(c.get("spend") or 0)
        score = float(c.get("score") or 0)
        high_visits = int(c.get("high_official_visits") or 0)
        roles = [
            {"role": t(x.get("role")), "visits": int(x.get("visits") or 0), "people": 0, "spend": 0}
            for x in (c.get("role_stats") or []) if t(x.get("role"))
        ]
        recent = [
            {
                "date": t(x.get("date")),
                "time": t(x.get("time")),
                "role": f"{t(x.get('institution'))} {t(x.get('role'))}".strip(),
                "people": int(x.get("people") or 0),
                "amount": int(x.get("amount") or 0),
                "purpose": t(x.get("purpose")),
                "source": t(x.get("source")),
            }
            for x in (c.get("recent") or [])
        ]
        out.append({
            "name": name,
            "origin": "법조·법률행정",
            "region": "전국",
            "jurisdiction": "대한민국",
            "institution": " · ".join(inst[:4]) or "법조·법률행정기관",
            "institutions": inst,
            "type": "executive",
            "destination": None,
            "executive": {
                "rank": rank,
                "score": round(score, 1),
                "exec_events": visits,
                "roles": int(c.get("role_count") or 0),
                "months": months,
                "evening_ratio": 0,
                "source": "justice_leadership",
                "top_official_visits": high_visits,
                "top_role_tier": t(c.get("top_role_tier")),
                "top_role_label": t(c.get("top_role")),
            },
            "address": address,
            "search_query": f"{display_name} {address or '대한민국'}",
            "business": {
                "display": display_name,
                "category": _category(name),
                "phone": t(override.get("phone")),
                "status": "법조·법률행정기관 공식 업무추진비 원자료상 사용처",
                "rating": "",
                "note": "법무부·법제처·검찰·법원·헌법재판소·공수처 등 고위직 공개 업무추진비에서 추출한 식사성 사용처입니다.",
                "url": t(override.get("url")),
                "verified_at": t(override.get("verified_at")),
                "verification_confidence": t(override.get("confidence")),
            },
            "evidence": {
                "visits": visits,
                "spend": spend,
                "people": 0,
                "months": months,
                "evening": 0,
                "evening_ratio": 0,
                "ppc": 0,
                "date_min": t(c.get("date_min")),
                "date_max": t(c.get("date_max")),
                "roles": roles,
                "purposes": c.get("purpose_stats") or [],
                "recent": recent,
                "source_rows": [],
            },
            "why": f"법조·법률행정 고위직 공개 업무추진비에서 {visits}회 확인된 사용처입니다. 고위직 직접 사용 신호는 {high_visits}회입니다.",
            "published_source": "justice_leadership",
            "cohort": "justice_leadership",
        })
    return out


def _legislator_record(c: dict, published_rank: int | None = None, qa_grade: str = "") -> dict:
    name = t(c.get("merchant"))
    address = t(c.get("address"))
    visits = int(c.get("visits") or 0)
    members = int(c.get("member_count") or 0)
    months = int(c.get("months") or 0)
    score = float(c.get("score") or 0)
    spend = int(c.get("spend") or 0)
    recent = [
        {
            "date": t(x.get("date")),
            "time": "",
            "role": f"국회의원 {t(x.get('member'))}",
            "people": 0,
            "amount": int(x.get("amount") or 0),
            "purpose": t(x.get("purpose")),
            "source": t(x.get("source")),
        }
        for x in (c.get("recent") or [])
    ]
    roles = [
        {"role": f"국회의원 {m}", "visits": 0, "people": 0, "spend": 0}
        for m in (c.get("members") or [])[:20]
    ]
    rank = int(published_rank or c.get("candidate_rank") or 0)
    return {
        "name": name,
        "origin": "국회의원(정치자금 2024)",
        "region": "전국",
        "jurisdiction": "대한민국",
        "institution": "국회의원",
        "type": "executive",
        "destination": None,
        "executive": {
            "rank": rank,
            "score": round(score, 1),
            "exec_events": visits,
            "roles": members,
            "months": months,
            "evening_ratio": 0,
            "source": "national_legislator_2024",
        },
        "address": address,
        "search_query": f"{name} {address or '대한민국'}",
        "business": {
            "display": name,
            "category": _category(name),
            "phone": "",
            "status": f"2024년 국회의원 정치자금 지출내역 사용처 · 지도 QA {qa_grade or '대기'}",
            "rating": "",
            "note": "중앙선관위 회계보고서를 정보공개로 확보해 오마이뉴스·경향신문·뉴스타파가 OCR/정제한 2024 데이터의 식사성 지출 후보. 최신 2026 현황이 아니라 historical signal입니다.",
            "url": "https://github.com/OhmyNews/KA-money",
        },
        "evidence": {
            "visits": visits,
            "spend": spend,
            "people": 0,
            "months": months,
            "evening": 0,
            "evening_ratio": 0,
            "ppc": 0,
            "date_min": t(c.get("date_min")),
            "date_max": t(c.get("date_max")),
            "roles": roles,
            "purposes": c.get("purpose_stats") or [],
            "recent": recent,
            "source_rows": [],
        },
        "why": f"2024년 국회의원 정치자금 지출자료에서 {visits}회, {members}명의 의원에게서 반복 확인된 사용처입니다. 정치적 평가가 아닌 식당 선택 패턴 신호입니다.",
        "published_source": "national_legislator_2024",
        "cohort": "national_legislator",
        "historical": True,
        "qa_grade": qa_grade,
    }


def legislator_candidate_records(max_records: int = 200) -> list[dict]:
    """All pre-QA candidates used only for geocoding/review, never directly published."""
    d = _legislator_candidate_doc()
    out = []
    for rank, c in enumerate((d.get("candidates") or [])[:max_records], 1):
        if not t(c.get("merchant")):
            continue
        row = dict(c)
        row["candidate_rank"] = rank
        out.append(_legislator_record(row, published_rank=rank, qa_grade="CANDIDATE"))
    return out


def legislator_records(max_records: int = 80) -> list[dict]:
    """Public legislator records are selected exclusively by the QA report."""
    cdoc = _legislator_candidate_doc()
    qdoc = _legislator_qa_doc()
    if not cdoc or not qdoc or not qdoc.get("passed"):
        return []

    by_name = {t(c.get("merchant")): c for c in (cdoc.get("candidates") or []) if t(c.get("merchant"))}
    out = []
    for qa in (qdoc.get("approved") or [])[:max_records]:
        name = t(qa.get("merchant"))
        c = by_name.get(name)
        if not c:
            continue
        merged = dict(c)
        merged["address"] = t(qa.get("address")) or t(c.get("address"))
        merged["candidate_rank"] = int(qa.get("candidate_rank") or 0)
        out.append(_legislator_record(
            merged,
            published_rank=int(qa.get("published_rank") or len(out) + 1),
            qa_grade=t(qa.get("grade")),
        ))
    return out


def merge_extra_published(payload: dict) -> dict:
    payload = dict(payload)
    base = list(payload.get("records", []))
    seen = {(t(r.get("name")), t(r.get("origin"))) for r in base}
    added = []
    for r in central_records() + justice_records() + legislator_records():
        k = (t(r.get("name")), t(r.get("origin")))
        if k in seen:
            continue
        seen.add(k)
        added.append(r)

    records = base + added
    payload["records"] = records
    payload["origins"] = sorted({t(r.get("origin")) for r in records if t(r.get("origin"))})

    stats = dict(payload.get("stats") or {})
    stats["total"] = len(records)
    stats["supplemental"] = int(stats.get("supplemental") or 0) + len(added)
    stats["executive"] = sum(bool(r.get("executive")) for r in records)
    stats["destination"] = sum(bool(r.get("destination")) for r in records)
    stats["both"] = sum(bool(r.get("destination")) and bool(r.get("executive")) for r in records)
    payload["stats"] = stats

    meta = dict(payload.get("meta") or {})
    ps = dict(meta.get("published_supplements") or {})
    ps["central_executive"] = sum(r.get("published_source") == "central_executive" for r in added)
    ps["justice_leadership"] = sum(r.get("published_source") == "justice_leadership" for r in added)
    ps["national_legislator_2024"] = sum(r.get("published_source") == "national_legislator_2024" for r in added)
    meta["published_supplements"] = ps
    meta["scope"] = "수도권·중앙정부·법조·국회 공공부문 Executive Dining"
    payload["meta"] = meta
    return payload
