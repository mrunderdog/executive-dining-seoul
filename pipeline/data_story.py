"""Build traceable source and publication metrics for the public site's data-story panel.

Every numeric output is computed from the exact records sent to the browser, or
from the current quality-gate report. Raw ingestion rows are intentionally excluded:
raw records across origins cannot be added without proving deduplication.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone

GROUP_ORDER = (
    "수도권 지방의회",
    "광역 집행부",
    "중앙정부",
    "국회의원 정치자금",
    "공기업·공공기관",
    "법조·법률행정",
    "교육·치안",
    "기타 공식 출처",
)
ATTENTION_DIAGNOSES = {
    "PUBLISH_PIPELINE_REVIEW",
    "CANDIDATE_BUILD_REVIEW",
    "ROLE_OR_SOURCE_SCOPE_REVIEW",
    "INGESTION_REVIEW",
    "DISCOVERY_REVIEW",
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _origin_group(origin: str) -> str:
    label = str(origin or "").strip()
    if label.startswith("국회의원"):
        return "국회의원 정치자금"
    if label in {"서울시청", "경기도청", "인천시청"} or "광역 집행부" in label:
        return "광역 집행부"
    if label.startswith("중앙정부"):
        return "중앙정부"
    if any(word in label for word in ("공기업", "공공기관")):
        return "공기업·공공기관"
    if any(word in label for word in ("법조", "법률행정", "법무행정")):
        return "법조·법률행정"
    if any(word in label for word in ("교육청", "경찰청", "경찰")):
        return "교육·치안"
    if any(word in label for word in ("의회", "구,", "구·", "시의회")) or label.endswith("구"):
        return "수도권 지방의회"
    return "기타 공식 출처"


def _last_record_date(records: list[dict]) -> str | None:
    days = []
    today = datetime.now(timezone.utc).date()
    for record in records:
        candidate = str((record.get("evidence") or {}).get("date_max") or "")
        if not DATE_RE.fullmatch(candidate):
            continue
        try:
            day = datetime.strptime(candidate, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day <= today:
            days.append(candidate)
    return max(days) if days else None


def build_data_story(records: list[dict], quality: dict | None, built_at: str) -> dict:
    """Use the already published/map-annotated records, not potential candidates."""
    groups = Counter()
    for record in records:
        origins = record.get("origins") or ([record.get("origin")] if record.get("origin") else [])
        # One entity can represent multiple origin families; never sum groups into a site total.
        kinds = {_origin_group(origin) for origin in origins if str(origin or "").strip()}
        for kind in kinds:
            groups[kind] += 1

    quality_available = isinstance(quality, dict) and isinstance(quality.get("passed"), bool)
    health = ((quality or {}).get("checks") or {}).get("source_health") or {}
    if not isinstance(health, dict):
        health = {}
    diagnoses = Counter(str((entry or {}).get("diagnosis") or "UNKNOWN")
                        for entry in health.values() if isinstance(entry, dict))
    attention = sum(diagnoses[kind] for kind in ATTENTION_DIAGNOSES)

    return {
        "generated_at_utc": built_at,
        "latest_disclosed_record_date": _last_record_date(records),
        "source_groups": [{"label": name, "published_venues": groups[name]}
                          for name in GROUP_ORDER if groups[name] > 0],
        "source_group_semantics": "원자료 건수가 아니라 해당 출처군의 공개 식당 수. 기관 간 중복 식당은 각각에 포함되므로 합산 불가.",
        "published": {
            "venues": len(records),
            "with_address": sum(bool(str(row.get("address") or "").strip()) for row in records),
            "mapped": sum(
                isinstance(row.get("lat"), (float, int)) and
                isinstance(row.get("lon"), (float, int))
                for row in records
            ),
            "cross_institution": sum(bool((row.get("cross_institution") or {}).get("is_cross")) for row in records),
            "top_official": sum(
                int((row.get("executive") or {}).get("top_official_visits") or 0) > 0
                for row in records
            ),
        },
        "health": {
            "qa_passed": quality.get("passed") if quality_available else None,
            "qa_warning_count": len(quality.get("warnings") or []) if quality_available else None,
            "diagnosed_sources": len(health) if quality_available else None,
            "diagnosis_counts": dict(sorted(diagnoses.items())),
            "attention_sources": attention if quality_available else None,
            "confirmed_refresh_failures": None,
            "diagnostic_scope": "quality_gate의 수도권 의회 source 진단. 전체 출처의 장애 집계가 아님.",
            "failure_scope": "실제 최신 수집 실패 이력은 통합 이벤트 로그가 없어 미집계.",
        },
        "limitations": [
            "공식 지출 원자료에 식당이 등장하는 사실과 개인의 직접 참석은 다릅니다.",
            "식당 위치 확인은 카드 결제 가맹점의 법적 동일성 또는 개별 지점을 보증하지 않습니다.",
            "사이트 생성 시각은 원천자료 갱신 시각이나 GitHub Pages 배포 완료 시각이 아닙니다.",
        ],
    }
