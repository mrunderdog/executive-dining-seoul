#!/usr/bin/env python3
"""P4: rank public dining venues missing safe map coordinates.

Review-only. Never infer a branch from a matching name, auto-geocode national
unknown locations, or equate an expense account with an individual's attendance.
Uses exactly the published dataset merge and coordinate selection paths.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from coordinate_selection import select_coordinate
from data_io import load_payload
from extra_published import merge_extra_published
from global_entities import merge_global_entities
from published_sources import merge_published_sources

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "geocode_cache.json"


def text(value):
    return " ".join(str(value or "").split()).strip()


def geo_cache(path=CACHE):
    doc = json.loads(path.read_text(encoding="utf-8"))
    return doc.get("records", doc) if isinstance(doc, dict) else {}


def mapped(record, geo):
    if (record.get("source_verified_coordinate")
            and isinstance(record.get("lat"), (int, float))
            and isinstance(record.get("lon"), (int, float))):
        return True
    return select_coordinate(record, geo)[1] is not None


def source_urls(record):
    urls = []
    recent = (record.get("evidence") or {}).get("recent") or []
    for item in recent:
        u = text(item.get("source")) if isinstance(item, dict) else ""
        p = urlparse(u)
        if p.scheme == "https" and p.hostname and u not in urls:
            urls.append(u)
    return urls[:5]


def assess(record):
    evidence = record.get("evidence") or {}
    visits = max(0, int(evidence.get("visits") or 0))
    months = max(0, int(evidence.get("months") or 0))
    spend = max(0, int(evidence.get("spend") or 0))
    origins = [text(v) for v in (record.get("origins") or []) if text(v)]
    institutions = [text(v) for v in (record.get("institutions") or []) if text(v)]
    origin_count = max(1, len(set(origins)))
    institution_count = max(1, len(set(institutions)))
    addr = text(record.get("address"))
    links = source_urls(record)
    venue_evidence = [x for x in (record.get("venue_location_evidence_urls") or [])
                      if isinstance(x, str) and x.startswith("https://")]
    if addr and venue_evidence and record.get("venue_location_match_basis"):
        reason = "APPROVED_VENUE_ADDRESS_NEEDS_SAFE_COORDINATE"
    elif addr:
        reason = "PUBLISHED_ADDRESS_NEEDS_GEOCODE_OR_IDENTITY_REVIEW"
    elif links:
        reason = "OFFICIAL_EXPENSE_SOURCE_MUST_BE_CHECKED_FOR_ADDRESS"
    else:
        reason = "MISSING_ADDRESS_AND_TRACEABLE_SOURCE"

    # Strong expense signals plus independent organizations drive review order.
    # A usable documented address/source increases feasibility, not evidence
    # of an individual's presence or of the card merchant branch.
    score = round(
        22 * math.log1p(visits)
        + 14 * min(5, institution_count - 1)
        + 18 * min(4, origin_count - 1)
        + 3 * min(12, months)
        + 2 * math.log1p(spend / 100_000)
        + (18 if addr else 0)
        + (5 if venue_evidence else 0)
        + (5 if links else 0),
        2,
    )
    return {
        "id": text(record.get("id")),
        "merchant": text(record.get("name")),
        "origin": text(record.get("origin")),
        "jurisdiction": text(record.get("jurisdiction")),
        "published_source": text(record.get("published_source")),
        "published_address": addr,
        "disclosed_usage_events": visits,
        "disclosed_spend_krw": spend,
        "months": months,
        "source_origin_count": origin_count,
        "listed_institution_count": institution_count,
        "review_priority_score": score,
        "source_urls": links,
        "venue_address_evidence_urls": venue_evidence,
        "review_status": reason,
        "payment_branch_verified": False,
        "individual_attendance_verified": False,
        "location_promoted": False,
    }


def build(records, geo, limit=50):
    if not 1 <= limit <= 500:
        raise ValueError("limit outside 1..500")
    all_records = list(records)
    missing = [assess(r) for r in all_records if not mapped(r, geo)]
    missing.sort(key=lambda x: (
        -x["review_priority_score"], -x["source_origin_count"],
        -x["disclosed_usage_events"], x["merchant"], x["origin"]
    ))
    queue = missing[:limit]
    return {
        "schema_version": 1,
        "purpose": "P4 top unmapped venue address and branch evidence review queue",
        "policy": "Research queue only. No auto-publication, name-only location guesses, card-merchant equivalence or personal-attendance claims.",
        "total_published_venues": len(all_records),
        "safe_map_venues": len(all_records) - len(missing),
        "unmapped_venues": len(missing),
        "reviewed_in_queue": len(queue),
        "unmapped_reason_counts": dict(sorted(Counter(x["review_status"] for x in missing).items())),
        "selected_reason_counts": dict(sorted(Counter(x["review_status"] for x in queue).items())),
        "approved_for_map_addition": 0,
        "candidates": queue,
    }


def markdown(doc):
    result = [
        "# P4 — 지도 미표시 식당 우선 검증 50곳",
        "",
        f"- 전체 식당: **{doc['total_published_venues']}**",
        f"- 안전하게 지도 표시: **{doc['safe_map_venues']}**",
        f"- 지도 미표시: **{doc['unmapped_venues']}**",
        f"- 이번 검증 대기열: **{doc['reviewed_in_queue']}곳**",
        "- 자동 지도 승격: **0곳** (장소·지점 근거 확보 후 별도 심사)",
        "",
        "## 기준",
        "",
        "공식 지출자료에 나온 **사용처 건수**·기관 교차·지출월·금액 및 확인 가능한 원문 링크를 기준으로 정렬합니다.",
        "사용처 발생 건수는 특정 공직자의 개인 방문 횟수가 아닙니다. 식당 주소 및 인허가 일치는 카드 승인 가맹점 동일성을 증명하지 않습니다.",
        "",
        "## 상위 50곳",
        "",
        "| # | 업소명 | 출처 | 집행 건수 | 기관/원천 수 | 상태 |",
        "|---:|---|---|---:|---|---|",
    ]
    for i, row in enumerate(doc["candidates"], 1):
        institution = f"{row['listed_institution_count']}/{row['source_origin_count']}"
        fields = [
            str(i), row["merchant"], row["origin"],
            str(row["disclosed_usage_events"]), institution, row["review_status"]
        ]
        result.append("| " + " | ".join(str(x).replace("|", "/").replace("\n", " ") for x in fields) + " |")
    result += [
        "",
        "## 승인 게이트",
        "",
        "1. 원천 파일의 동일 행에 주소가 있는지 확인하거나 독립적인 지점 소재지 증거 두 건 이상 확보",
        "2. 동명 업체·복수 지점·폐업 가능성 검토. LOCALDATA 인허가 위치만으로 카드 결제 지점 동일성 주장 금지",
        "3. 기존 지도 식당과 주소·지점 기준 중복 검사",
        "4. 안전한 도로명 주소 지오코딩을 검증한 뒤에만 지도 반영. 불충분하면 대기 상태 유지",
        "",
    ]
    return "\n".join(result)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--output", default="reports/p4-unmapped-venue-review.json")
    p.add_argument("--markdown", default="reports/p4-unmapped-venue-review.md")
    args = p.parse_args()
    records = merge_global_entities(merge_extra_published(merge_published_sources(load_payload())))["records"]
    doc = build(records, geo_cache(), args.limit)
    target = ROOT / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = ROOT / args.markdown
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(markdown(doc), encoding="utf-8")
    print(json.dumps({k: v for k, v in doc.items() if k != "candidates"}, ensure_ascii=False))
    print("Top 10:", json.dumps(doc["candidates"][:10], ensure_ascii=False))


if __name__ == "__main__":
    main()
