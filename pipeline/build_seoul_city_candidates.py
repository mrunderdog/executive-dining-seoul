#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "seoul_city_hall_expense.json"
REPORTS = ROOT / "reports"

MEAL_WORDS = (
    "간담", "오찬", "만찬", "식사", "회의", "협의", "논의", "격려", "소통",
    "업무협의", "현안", "관계자", "직원", "방문", "간담회",
)
EXCLUDE_WORDS = (
    "경조", "축의", "조의", "화환", "꽃", "주유", "주차", "택시", "교통",
    "온라인", "쿠팡", "네이버", "다이소", "문구", "물품", "기념품", "사무용",
    "다과", "차류", "커피", "카페", "스타벅스", "이디야", "베이커리", "빵",
    "상품권", "소속 상근직원",
)
SEOUL_DISTRICTS = (
    "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구",
    "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구",
    "구로구", "금천구", "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구",
)
CENTRAL_ADJACENT = {"종로구", "서대문구", "용산구"}
CAPITAL_PREFIXES = ("경기 ", "경기도 ", "인천 ", "인천광역시 ")
NATIONAL_PREFIXES = (
    "부산 ", "부산광역시 ", "대구 ", "대구광역시 ", "대전 ", "대전광역시 ",
    "광주 ", "광주광역시 ", "울산 ", "울산광역시 ", "세종 ", "세종특별자치시 ",
    "강원 ", "강원특별자치도 ", "충북 ", "충청북도 ", "충남 ", "충청남도 ",
    "전북 ", "전북특별자치도 ", "전남 ", "전라남도 ", "경북 ", "경상북도 ",
    "경남 ", "경상남도 ", "제주 ", "제주특별자치도 ",
)


def txt(v) -> str:
    return " ".join(str(v or "").replace("\n", " ").split()).strip()


def canonical_name(v: str) -> str:
    return txt(v).strip(" ,")


def canonical_address(v: str) -> str:
    s = txt(v).strip(" ,")
    if not s:
        return ""
    s = s.replace("서울특별시", "서울").replace("서울시", "서울")
    s = re.sub(r"\s*,\s*", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" ,")
    if any(s.startswith(d + " ") or s == d for d in SEOUL_DISTRICTS):
        s = "서울 " + s
    s = re.sub(r"^서울\s+서울\s+", "서울 ", s)
    return s


def district_from_address(address: str) -> str:
    a = canonical_address(address)
    for d in SEOUL_DISTRICTS:
        if re.search(rf"(?:^|\s){re.escape(d)}(?:\s|$)", a):
            return d
    return ""


def location_bucket(address: str) -> tuple[str, float]:
    a = canonical_address(address)
    if not a:
        return "unknown", 0.0
    district = district_from_address(a)
    if district == "중구":
        return "city_hall_home", 0.0
    if district in CENTRAL_ADJACENT:
        return "central_adjacent", 0.2
    if district:
        return "seoul_cross_district", 0.65
    # Only treat an explicit administrative-area prefix as evidence of travel.
    # This avoids false positives such as '세종대로' being interpreted as Sejong City.
    if a.startswith(CAPITAL_PREFIXES):
        return "capital_region_destination", 0.85
    if a.startswith(NATIONAL_PREFIXES):
        return "national_destination", 1.0
    return "unknown", 0.0


def merchant_key(row: dict) -> str:
    name = canonical_name(row.get("merchant"))
    address = canonical_address(row.get("address"))
    return f"{name}||{address}" if address else f"{name}||UNKNOWN"


def looks_like_meal(row: dict) -> bool:
    purpose = txt(row.get("purpose"))
    merchant = txt(row.get("merchant"))
    combined = f"{purpose} {merchant}"
    if not merchant or any(word in combined for word in EXCLUDE_WORDS):
        return False
    return any(word in purpose for word in MEAL_WORDS)


def evening(row: dict) -> bool:
    m = re.match(r"\s*(\d{1,2}):", txt(row.get("used_time")))
    return bool(m and int(m.group(1)) >= 17)


def executive_score(visits: int, departments: int, months: int, spend: int, evening_ratio: float) -> float:
    repeat = min(math.log1p(visits) / math.log1p(15), 1.0)
    dept = min(math.log1p(departments) / math.log1p(8), 1.0)
    month = min(months / 8, 1.0)
    spend_norm = min(math.log1p(max(spend, 0)) / math.log1p(5_000_000), 1.0)
    return round(100 * (0.35 * repeat + 0.30 * dept + 0.15 * month + 0.10 * spend_norm + 0.10 * evening_ratio), 1)


def destination_score(visits: int, departments: int, months: int, evening_ratio: float, destination_weight: float) -> float:
    repeat = min(math.log1p(visits) / math.log1p(8), 1.0)
    dept = min(math.log1p(departments) / math.log1p(6), 1.0)
    month = min(months / 6, 1.0)
    return round(100 * (0.50 * destination_weight + 0.20 * repeat + 0.15 * dept + 0.10 * month + 0.05 * evening_ratio), 1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build exploratory Seoul City Hall restaurant candidates.")
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--min-visits", type=int, default=3)
    ap.add_argument("--min-months", type=int, default=2)
    args = ap.parse_args()

    if not RAW.exists():
        raise SystemExit(f"missing raw source: {RAW}")
    doc = json.loads(RAW.read_text(encoding="utf-8"))
    rows = [r for r in doc.get("rows", []) if r.get("date_quality") == "in_period" and looks_like_meal(r)]

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[merchant_key(r)].append(r)

    out = []
    for _, items in groups.items():
        name = canonical_name(items[0].get("merchant"))
        address_variants = [txt(r.get("address")) for r in items if txt(r.get("address"))]
        canonical_variants = [canonical_address(x) for x in address_variants if canonical_address(x)]
        address = Counter(canonical_variants).most_common(1)[0][0] if canonical_variants else ""
        visits = len(items)
        months_set = sorted({(r.get("used_date") or "")[:7] for r in items if re.match(r"20\d{2}-\d{2}", r.get("used_date") or "")})
        departments = sorted({txt(r.get("department")) for r in items if txt(r.get("department"))})
        spend = sum(int(r.get("amount") or 0) for r in items)
        people_known = [int(r.get("people")) for r in items if isinstance(r.get("people"), int) and r.get("people") >= 0]
        evening_count = sum(evening(r) for r in items)
        evening_ratio = evening_count / visits if visits else 0
        bucket, destination_weight = location_bucket(address)
        ex_score = executive_score(visits, len(departments), len(months_set), spend, evening_ratio)
        dest_score = destination_score(visits, len(departments), len(months_set), evening_ratio, destination_weight)

        dept_counter = Counter(txt(r.get("department")) for r in items if txt(r.get("department")))
        dept_spend = defaultdict(int)
        for r in items:
            d = txt(r.get("department"))
            if d:
                dept_spend[d] += int(r.get("amount") or 0)
        department_stats = [
            {"department": d, "visits": n, "spend": dept_spend[d]}
            for d, n in dept_counter.most_common(12)
        ]
        purpose_counter = Counter(txt(r.get("purpose")) for r in items if txt(r.get("purpose")))
        purpose_stats = [{"text": p, "count": n} for p, n in purpose_counter.most_common(8)]
        recent = [
            {
                "date": txt(r.get("used_date")),
                "time": txt(r.get("used_time")),
                "department": txt(r.get("department")),
                "people": int(r.get("people") or 0),
                "amount": int(r.get("amount") or 0),
                "purpose": txt(r.get("purpose")),
                "source": txt(r.get("source_document_url")) or txt(r.get("source_dataset_url")),
            }
            for r in sorted(items, key=lambda x: (x.get("used_date") or "", x.get("used_time") or ""), reverse=True)[:8]
        ]
        dates = sorted(r.get("used_date") for r in items if r.get("used_date"))

        out.append({
            "merchant": name,
            "address": address,
            "address_variants": list(dict.fromkeys(address_variants))[:6],
            "district": district_from_address(address),
            "location_bucket": bucket,
            "destination_weight": destination_weight,
            "score": ex_score,
            "executive_score": ex_score,
            "destination_score": dest_score,
            "visits": visits,
            "departments": departments,
            "department_count": len(departments),
            "department_stats": department_stats,
            "months": len(months_set),
            "spend": spend,
            "known_people": sum(people_known),
            "evening_ratio": round(evening_ratio, 3),
            "date_min": dates[0] if dates else "",
            "date_max": dates[-1] if dates else "",
            "purpose_stats": purpose_stats,
            "recent": recent,
        })

    executive_eligible = [x for x in out if x["visits"] >= args.min_visits and x["months"] >= args.min_months]
    executive_eligible.sort(key=lambda x: (x["executive_score"], x["department_count"], x["visits"], x["spend"]), reverse=True)

    destination_eligible = [
        x for x in out
        if x["destination_weight"] >= 0.65 and x["visits"] >= 2 and x["months"] >= 2
    ]
    destination_eligible.sort(key=lambda x: (x["destination_score"], x["visits"], x["department_count"]), reverse=True)

    # Current public schema uses name+origin as the entity key, so keep only the strongest
    # branch for a repeated merchant name. Branch evidence remains available in the raw analysis.
    best_by_name: dict[str, dict] = {}
    for x in executive_eligible[:args.top] + destination_eligible[:args.top]:
        strength = max(float(x.get("executive_score") or 0), float(x.get("destination_score") or 0))
        old = best_by_name.get(x["merchant"])
        old_strength = max(float(old.get("executive_score") or 0), float(old.get("destination_score") or 0)) if old else -1
        if old is None or strength > old_strength or (strength == old_strength and x["visits"] > old["visits"]):
            best_by_name[x["merchant"]] = x
    union = sorted(
        best_by_name.values(),
        key=lambda x: (max(x["executive_score"], x["destination_score"]), x["visits"], x["department_count"]),
        reverse=True,
    )

    REPORTS.mkdir(parents=True, exist_ok=True)
    js = REPORTS / "seoul-city-hall-executive-candidates.json"
    js.write_text(json.dumps({
        "source": "seoul_city_hall",
        "cohort": "regional_executive",
        "entity_count": len(out),
        "executive_eligible_count": len(executive_eligible),
        "destination_eligible_count": len(destination_eligible),
        "publication_status": "staged_not_published",
        "candidates": union,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    md = REPORTS / "seoul-city-hall-executive-candidates.md"
    lines = [
        "# Seoul City Hall Executive Dining candidates",
        "",
        f"- Meal-like rows considered: **{len(rows)}**",
        f"- Canonical merchant/address entities: **{len(out)}**",
        f"- Executive eligible: **{len(executive_eligible)}**",
        f"- Destination eligible: **{len(destination_eligible)}**",
        "",
        "> Executive score measures repeated selection, department diversity, persistence, spend and evening use.",
        "> Destination score separately rewards addresses outside Seoul City Hall's home district. It is an exploration signal, not a food-quality rating.",
        "",
        "## Executive Repeat",
        "",
        "| # | Merchant | Address | Score | Visits | Departments | Months | Spend | Evening |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for i, x in enumerate(executive_eligible[:args.top], 1):
        lines.append(
            f"| {i} | {x['merchant'].replace('|','/')} | {x['address'].replace('|','/')} | {x['executive_score']:.1f} | "
            f"{x['visits']} | {x['department_count']} | {x['months']} | {x['spend']:,} | {x['evening_ratio']:.0%} |"
        )
    lines += [
        "",
        "## Destination VIP",
        "",
        "| # | Merchant | Address | Score | Zone | Visits | Departments | Months | Spend |",
        "|---:|---|---|---:|---|---:|---:|---:|---:|",
    ]
    for i, x in enumerate(destination_eligible[:args.top], 1):
        lines.append(
            f"| {i} | {x['merchant'].replace('|','/')} | {x['address'].replace('|','/')} | {x['destination_score']:.1f} | "
            f"{x['location_bucket']} | {x['visits']} | {x['department_count']} | {x['months']} | {x['spend']:,} |"
        )
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "source": "seoul_city_hall",
        "meal_rows": len(rows),
        "entities": len(out),
        "executive_eligible": len(executive_eligible),
        "destination_eligible": len(destination_eligible),
        "top_executive": executive_eligible[:5],
        "top_destination": destination_eligible[:5],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
