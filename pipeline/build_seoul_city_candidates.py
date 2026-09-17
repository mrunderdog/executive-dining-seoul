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


def txt(v) -> str:
    return " ".join(str(v or "").split()).strip()


def merchant_key(row: dict) -> str:
    name = txt(row.get("merchant"))
    address = txt(row.get("address"))
    return f"{name}||{address}" if address else name


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


def outside_seoul(address: str) -> bool | None:
    a = txt(address)
    if not a:
        return None
    if "서울" in a or re.search(r"(종로|중|용산|성동|광진|동대문|중랑|성북|강북|도봉|노원|은평|서대문|마포|양천|강서|구로|금천|영등포|동작|관악|서초|강남|송파|강동)구", a):
        return False
    if any(x in a for x in ("경기", "인천", "부산", "대구", "대전", "광주", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주")):
        return True
    return None


def score(visits: int, departments: int, months: int, spend: int, evening_ratio: float, outside_ratio: float) -> float:
    repeat = min(math.log1p(visits) / math.log1p(15), 1.0)
    dept = min(math.log1p(departments) / math.log1p(8), 1.0)
    month = min(months / 8, 1.0)
    spend_norm = min(math.log1p(max(spend, 0)) / math.log1p(5_000_000), 1.0)
    outside = min(max(outside_ratio, 0.0), 1.0)
    return round(100 * (0.30 * repeat + 0.25 * dept + 0.15 * month + 0.10 * spend_norm + 0.10 * evening_ratio + 0.10 * outside), 1)


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
    for key, items in groups.items():
        name = txt(items[0].get("merchant"))
        address = Counter(txt(r.get("address")) for r in items if txt(r.get("address"))).most_common(1)
        address = address[0][0] if address else ""
        visits = len(items)
        months_set = sorted({(r.get("used_date") or "")[:7] for r in items if re.match(r"20\d{2}-\d{2}", r.get("used_date") or "")})
        departments = sorted({txt(r.get("department")) for r in items if txt(r.get("department"))})
        spend = sum(int(r.get("amount") or 0) for r in items)
        people_known = [int(r.get("people")) for r in items if isinstance(r.get("people"), int) and r.get("people") >= 0]
        evening_count = sum(evening(r) for r in items)
        evening_ratio = evening_count / visits if visits else 0

        outside_values = [outside_seoul(r.get("address") or "") for r in items]
        outside_known = [x for x in outside_values if x is not None]
        outside_ratio = (sum(1 for x in outside_known if x) / len(outside_known)) if outside_known else 0.0

        s = score(visits, len(departments), len(months_set), spend, evening_ratio, outside_ratio)
        out.append({
            "merchant": name,
            "address": address,
            "score": s,
            "visits": visits,
            "departments": departments,
            "department_count": len(departments),
            "months": len(months_set),
            "spend": spend,
            "known_people": sum(people_known),
            "evening_ratio": round(evening_ratio, 3),
            "outside_seoul_ratio": round(outside_ratio, 3),
            "sample_purposes": list(dict.fromkeys(txt(r.get("purpose")) for r in items if txt(r.get("purpose"))))[:5],
            "sample_source_urls": list(dict.fromkeys(txt(r.get("source_document_url")) for r in items if txt(r.get("source_document_url"))))[:3],
        })

    out.sort(key=lambda x: (x["score"], x["department_count"], x["visits"], x["spend"]), reverse=True)
    eligible = [x for x in out if x["visits"] >= args.min_visits and x["months"] >= args.min_months]

    REPORTS.mkdir(parents=True, exist_ok=True)
    js = REPORTS / "seoul-city-hall-executive-candidates.json"
    js.write_text(json.dumps({
        "source": "seoul_city_hall",
        "cohort": "regional_executive",
        "candidate_count": len(out),
        "eligible_count": len(eligible),
        "publication_status": "staged_not_published",
        "candidates": eligible[:args.top],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    md = REPORTS / "seoul-city-hall-executive-candidates.md"
    lines = [
        "# Seoul City Hall Executive Dining candidates",
        "",
        f"- Meal-like rows considered: **{len(rows)}**",
        f"- Merchant/address entities: **{len(out)}**",
        f"- Eligible (visits ≥ {args.min_visits}, months ≥ {args.min_months}): **{len(eligible)}**",
        "",
        "> Exploratory signal only. Score measures repeated executive-branch selection, department diversity, persistence, spend, evening use and out-of-Seoul destination evidence. It is not a food-quality rating.",
        "> Candidates remain staged until entity/branch matching and geocoding pass.",
        "",
        "| # | Merchant | Address | Score | Visits | Departments | Months | Spend | Evening | Outside Seoul |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for i, x in enumerate(eligible[:args.top], 1):
        lines.append(
            f"| {i} | {x['merchant'].replace('|','/')} | {x['address'].replace('|','/')} | {x['score']:.1f} | "
            f"{x['visits']} | {x['department_count']} | {x['months']} | {x['spend']:,} | "
            f"{x['evening_ratio']:.0%} | {x['outside_seoul_ratio']:.0%} |"
        )
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "source": "seoul_city_hall",
        "meal_rows": len(rows),
        "entities": len(out),
        "eligible": len(eligible),
        "top": eligible[:5],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
