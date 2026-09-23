#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"

MEAL_WORDS = ("간담", "식사", "오찬", "만찬", "업무", "협의", "논의", "의정", "관계자", "현안", "의견", "격려", "소통")
EXCLUDE_WORDS = ("마트", "편의점", "문구", "주유", "주차", "택시", "철도", "고속도로", "온라인", "네이버", "쿠팡", "다이소", "꽃", "화원", "기념품", "구입", "물품", "카페", "커피", "스타벅스", "이디야", "베이커리", "빵", "사무실")
AMBIGUOUS_MERCHANTS = ("(주)신화푸드", "신화푸드")
NON_DINING_MERCHANT_WORDS = (
    "은행", "카드", "캐피탈", "렌터카", "렌트카", "보험", "증권", "저축은행",
    "주유소", "충전소", "철도", "코레일", "고속도로", "톨게이트", "택시",
    "인쇄", "광고", "디자인", "문구", "사무용", "우체국", "택배", "통신",
    "마트", "슈퍼", "편의점", "백화점", "면세점", "꽃집", "화원", "기념품",
    "후원회", "정당", "위원회", "의원실", "연구소", "포럼",
    "파리바게뜨", "뚜레쥬르", "배스킨라빈스", "적십자사", "적십자", "국군복지단",
    "부의금", "조의금", "축의금", "특별회비", "회비납부", "격려물품",
)

NON_MERCHANT_PATTERNS = (
    r"^의원\s*및\s*직원\s*\d+명$",
    r"^직원\s*\d+명$",
    r"^참석자\b.*$",
    r".*(?:간담회|회의|논의|협의|의정활동|현안).*(?:식비|다과비|지출).*$",
    r".*(?:식비|다과비)\s*지출.*$",
    r".*(?:특별)?회비\s*납부.*$",
    r"^(?:부의금|조의금|축의금)(?:\b|\().*$",
    r"^[가-힣]{1,2}\*{2}$",
)

ATTENDEE_TOKENS = (
    "의장", "부의장", "위원장", "의원", "동료의원", "직원",
    "의회사무국", "의정지원팀", "수행직원", "관계자", "대표단",
)


def normalize_merchant_name(value):
    s = " ".join(str(value or "").split())
    parts = s.split()
    # PDF extraction may put a space between every Hangul syllable.
    if len(parts) >= 3:
        singles = sum(bool(re.fullmatch(r"[가-힣]", p)) for p in parts)
        if singles / len(parts) >= 0.7:
            s = "".join(parts)
    return s


def plausible_merchant(value):
    s = normalize_merchant_name(value)
    if not s or s in {"-", "미상", "상호없음", "상호 없음", "확인불가", "확인 불가"}:
        return False
    if any(re.fullmatch(pattern, s) for pattern in NON_MERCHANT_PATTERNS):
        return False

    compact = re.sub(r"[\s,./·ㆍ()]+", "", s)
    # PDF table shifts often put the attendee column into merchant. These
    # strings are not businesses even when they contain many Hangul chars.
    has_headcount = bool(re.search(r"(?:\d+명|명\d+)", compact))
    attendee_hits = sum(token in compact for token in ATTENDEE_TOKENS)
    if has_headcount and attendee_hits:
        return False
    if "명" in compact and attendee_hits >= 2:
        return False

    purpose_markers = (
        "간담회식비", "식비지출", "다과비지출", "의정활동지원",
        "현안논의", "노고격려", "물품구입", "특별회비납부",
        "행사에따른관계자식비", "관계자식비",
    )
    if any(token in compact for token in purpose_markers):
        return False
    if len(compact) >= 16 and compact.endswith(("식비", "다과비")):
        return False
    if len(s) > 40 and any(word in s for word in ("간담회", "업무추진비", "의정활동", "직원", "의원")):
        return False
    return True


def plausible_transaction(row):
    amount = row.get("amount")
    people = row.get("people")
    if isinstance(amount, (int, float)) and isinstance(people, (int, float)):
        if amount > 0 and people >= 2 and amount / people < 1000:
            return False
    return True


def looks_meal(row):
    purpose = str(row.get("purpose") or "")
    merchant = normalize_merchant_name(row.get("merchant") or "")
    if not plausible_merchant(merchant):
        return False
    if merchant in AMBIGUOUS_MERCHANTS:
        return False
    if any(word in merchant for word in NON_DINING_MERCHANT_WORDS):
        return False
    if any(word in purpose + merchant for word in EXCLUDE_WORDS):
        return False
    return any(word in purpose for word in MEAL_WORDS) or bool(merchant)


def role_bucket(role, include_committees=False):
    s = re.sub(r"\s+", "", str(role or ""))
    if re.match(r"^의장(?:\(|$)", s):
        return "의장"
    if re.match(r"^(?:1|2)?부의장(?:\(|$)", s):
        return "부의장"
    if include_committees:
        m = re.match(r"^(.+위원장)(?:\(|$)", s)
        if m:
            return m.group(1)
    return None


def build_candidates(source):
    path = RAW / f"{source}_expense.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        row for row in data.get("rows", [])
        if row.get("date_quality") == "in_period"
        and looks_meal(row)
        and plausible_transaction(row)
    ]

    groups = defaultdict(list)
    include_committees = source in {"gyeonggi_council", "incheon_council"}
    leadership_rows = 0

    for row in rows:
        role = role_bucket(row.get("role"), include_committees=include_committees)
        if not role:
            role = role_bucket(row.get("source_sheet"), include_committees=include_committees)
        if not role:
            continue
        leadership_rows += 1
        name = normalize_merchant_name(row.get("merchant"))
        if not plausible_merchant(name):
            continue
        groups[name].append((role, row))

    out = []
    for name, items in groups.items():
        visits = len(items)
        roles = sorted({role for role, _ in items})
        spend = sum(int(row.get("amount") or 0) for _, row in items)
        people = sum(int(row.get("people") or 0) for _, row in items)
        months = sorted({
            (row.get("used_date") or "")[:7]
            for _, row in items
            if re.match(r"20\d{2}-\d{2}", row.get("used_date") or "")
        })
        evenings = 0
        for _, row in items:
            m = re.match(r"(\d{1,2})[:시]", str(row.get("used_time") or ""))
            if m and int(m.group(1)) >= 17:
                evenings += 1

        score = min(100, round(
            35 * min(visits / 10, 1)
            + 25 * min(len(months) / 5, 1)
            + 20 * min(len(roles) / 2, 1)
            + 10 * (evenings / visits if visits else 0)
            + 10 * min(spend / 3_000_000, 1),
            1,
        ))
        out.append({
            "merchant": name,
            "visits": visits,
            "roles": roles,
            "months": len(months),
            "spend": spend,
            "people": people,
            "evening_ratio": round(evenings / visits, 3) if visits else 0,
            "score": score,
        })

    out.sort(key=lambda x: (x["score"], x["visits"], x["spend"]), reverse=True)
    if leadership_rows >= 10 and not out:
        raise SystemExit(f"{source}: {leadership_rows} leadership rows but zero merchant candidates")
    return rows, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args()

    rows, out = build_candidates(args.source)
    REPORTS.mkdir(exist_ok=True)

    md = REPORTS / f"{args.source}-executive-candidates.md"
    lines = [
        f"# {args.source} Executive-repeat candidates",
        "",
        f"Rows considered: {len(rows)}",
        "",
        "> Exploratory candidate ranking only. It is not a food-quality score and is not yet published to the map.",
        "",
        "| # | Merchant | Score | Chair/Vice visits | Roles | Months | Spend | Evening |",
        "|---:|---|---:|---:|---|---:|---:|---:|",
    ]
    for i, item in enumerate(out[:args.top], 1):
        merchant = item["merchant"].replace("|", "/")
        roles = ", ".join(item["roles"])
        lines.append(
            f"| {i} | {merchant} | {item['score']:.1f} | {item['visits']} | "
            f"{roles} | {item['months']} | {item['spend']:,} | {item['evening_ratio']:.0%} |"
        )
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    js = REPORTS / f"{args.source}-executive-candidates.json"
    js.write_text(
        json.dumps({"source": args.source, "candidate_count": len(out), "candidates": out}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"source": args.source, "candidates": len(out), "top": out[:5]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
