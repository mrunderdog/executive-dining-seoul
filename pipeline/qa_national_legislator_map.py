#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
CANDIDATES = REPORTS / "national-legislator-candidates.json"
CACHE = ROOT / "data" / "geocode_cache.json"
OUT_JSON = REPORTS / "national-legislator-map-qa.json"
OUT_MD = REPORTS / "national-legislator-map-qa.md"

TARGET_PUBLISH = 80
MIN_APPROVED = 50

HARD_VETO = (
    "스타벅스", "카페", "커피", "현대그린푸드", "엘에스씨푸드", "국회의원식당",
    "구내식당", "후생복지", "푸드코트", "켄싱턴", "호텔", "리조트",
    "캐피탈", "렌터카", "렌탈", "보험", "은행", "카드", "증권", "정당", "후원회",
)


def t(v) -> str:
    return " ".join(str(v or "").split()).strip()


def norm(v) -> str:
    s = re.sub(r"^(?:주식회사|\(주\)|㈜|유한회사)\s*", "", t(v), flags=re.I)
    return re.sub(r"[^0-9a-z가-힣]", "", s.lower())


def distance_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2-lat1)
    dl = math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(a))


def cache_record(cache: dict, name: str):
    return (cache.get("records") or {}).get(f"{name}|국회의원(정치자금 2024)") or {}


def confidence(candidate: dict, geo: dict) -> tuple[str, list[str], bool]:
    reasons = []
    name = t(candidate.get("merchant"))
    address = t(candidate.get("address"))
    if any(x.lower() in name.lower() for x in HARD_VETO):
        return "F", ["non_restaurant_veto"], False
    if not geo or not isinstance(geo.get("lat"), (int, float)) or not isinstance(geo.get("lon"), (int, float)):
        return "D", ["no_coordinate"], False

    mode = t(geo.get("match_mode"))
    source = t(geo.get("source"))
    score = float(geo.get("score") or 0)
    display = t(geo.get("display_name"))
    result_name = t(geo.get("result_name"))
    wanted = norm(name)
    got = norm(result_name + " " + display)
    name_ok = bool(wanted and got and (wanted in got or got in wanted))

    if address and mode == "address":
        reasons.append("source_address_geocoded")
        # Address-only geocoding is trusted as location evidence; merchant identity is
        # already inherited from the source workbook's merchant/address pair.
        return "A", reasons, True

    if address and mode == "name_address" and name_ok:
        reasons.append("merchant_and_source_address_match")
        return "A", reasons, True

    if address and source == "arcgis" and score >= 95:
        reasons.append("high_score_address_match")
        return "B", reasons, True

    # Name-only matches are useful for review, but not safe enough for automatic public pins.
    if not address and mode == "name" and name_ok:
        reasons.append("name_only_no_source_address")
        if source == "arcgis" and score >= 98:
            return "C", reasons, False
        return "C", reasons, False

    reasons.append("ambiguous_entity_or_location")
    return "D", reasons, False


def main():
    if not CANDIDATES.exists():
        raise SystemExit(f"missing {CANDIDATES}")
    if not CACHE.exists():
        raise SystemExit(f"missing {CACHE}")

    doc = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    rows = []
    approved = []

    for rank, c in enumerate(doc.get("candidates") or [], 1):
        if rank > 200:
            break
        g = cache_record(cache, t(c.get("merchant")))
        grade, reasons, publishable = confidence(c, g)
        row = {
            "candidate_rank": rank,
            "merchant": t(c.get("merchant")),
            "merchant_variants": c.get("merchant_variants") or [],
            "address": t(c.get("address")),
            "score": float(c.get("score") or 0),
            "visits": int(c.get("visits") or 0),
            "member_count": int(c.get("member_count") or 0),
            "months": int(c.get("months") or 0),
            "spend": int(c.get("spend") or 0),
            "grade": grade,
            "publishable": bool(publishable),
            "qa_reasons": reasons,
            "geocode": {
                "lat": g.get("lat"),
                "lon": g.get("lon"),
                "source": g.get("source"),
                "match_mode": g.get("match_mode"),
                "score": g.get("score"),
                "query": g.get("query"),
                "display_name": g.get("display_name"),
                "result_name": g.get("result_name"),
                "failed": bool(g.get("failed")),
            },
        }
        rows.append(row)
        if publishable and len(approved) < TARGET_PUBLISH:
            row["published_rank"] = len(approved) + 1
            approved.append(row)

    grade_counts = {}
    for r in rows:
        grade_counts[r["grade"]] = grade_counts.get(r["grade"], 0) + 1

    result = {
        "schema_version": 1,
        "source": "national_legislator_2024",
        "reviewed_candidates": len(rows),
        "target_publish_count": TARGET_PUBLISH,
        "approved_count": len(approved),
        "grade_counts": grade_counts,
        "approved": approved,
        "qa_rows": rows,
        "passed": len(approved) >= MIN_APPROVED,
        "policy": {
            "A": "source address + geocode match; auto-publish",
            "B": "strong address-based match; auto-publish",
            "C": "name-only match without source address; review only, no public pin",
            "D": "missing/ambiguous coordinate; no publish",
            "F": "non-restaurant veto; no publish",
        },
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# National legislator map QA — 2024",
        "",
        f"- Reviewed candidates: **{len(rows)}**",
        f"- Approved for public map/list: **{len(approved)} / {TARGET_PUBLISH} target**",
        f"- Grade counts: **{grade_counts}**",
        f"- Gate: **{'PASS' if result['passed'] else 'FAIL'}** (minimum {MIN_APPROVED})",
        "",
        "## Fix / publication policy",
        "",
        "- A: source address geocoded or merchant+source-address matched → publish",
        "- B: strong address-based match → publish",
        "- C: name-only geocode without source address → QA list only; do not publish",
        "- D: missing/ambiguous coordinate → do not publish",
        "- F: non-restaurant/organizational merchant → do not publish",
        "",
        "## Approved",
        "",
        "| Pub | Cand | Merchant | Grade | Address | Visits | Members | Geocode |",
        "|---:|---:|---|---|---|---:|---:|---|",
    ]
    for x in approved:
        g = x["geocode"]
        md.append(
            f"| {x['published_rank']} | {x['candidate_rank']} | {x['merchant'].replace('|','/')} | {x['grade']} | "
            f"{x['address'].replace('|','/')} | {x['visits']} | {x['member_count']} | "
            f"{t(g.get('source'))}/{t(g.get('match_mode'))} |"
        )
    md += [
        "",
        "## Needs review / excluded",
        "",
        "| Cand | Merchant | Grade | Address | Reason | Geocode |",
        "|---:|---|---|---|---|---|",
    ]
    for x in rows:
        if x.get("publishable"):
            continue
        g = x["geocode"]
        md.append(
            f"| {x['candidate_rank']} | {x['merchant'].replace('|','/')} | {x['grade']} | "
            f"{x['address'].replace('|','/')} | {','.join(x['qa_reasons'])} | "
            f"{t(g.get('source'))}/{t(g.get('match_mode'))} {t(g.get('display_name')).replace('|','/')} |"
        )
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({
        "reviewed": len(rows),
        "approved": len(approved),
        "grades": grade_counts,
        "passed": result["passed"],
    }, ensure_ascii=False))
    if not result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
