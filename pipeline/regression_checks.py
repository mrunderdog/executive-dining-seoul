#!/usr/bin/env python3
"""Small dependency-free regression suite for bugs already seen in production."""
from pathlib import Path

from coordinate_selection import select_coordinate
from ingest_council_expense import map_columns, normalize_sheet, resolve_role

ROOT = Path(__file__).resolve().parents[1]


def test_role_column_priority():
    header = ["집행일자", "부서명", "사용자", "집행장소", "집행금액"]
    mapping = map_columns(header)
    assert mapping.get("role") == 2, mapping


def test_role_from_purpose():
    role = resolve_role("안성시의회", "Sheet1", "", purpose="의정활동 간담회 (의장)")
    assert role == "의장", role


def test_national_name_only_coordinate_is_suppressed():
    record = {
        "name": "낙원",
        "origin": "중앙정부",
        "jurisdiction": "대한민국",
        "cohort": "central_executive",
        "address": "",
    }
    geo = {
        "낙원|중앙정부": {
            "lat": 37.2800,
            "lon": 127.0179,
            "match_mode": "name",
            "addr_type": "POI",
            "query": "낙원 대한민국",
            "display_name": "낙원",
            "score": 100,
        }
    }
    key, row, meta = select_coordinate(record, geo)
    assert key is None and row is None, (key, row)
    assert any(x.get("reason") == "national_record_without_verified_address"
               for x in meta.get("rejected_candidates", [])), meta


def test_address_mismatch_coordinate_is_suppressed():
    record = {
        "name": "테스트식당",
        "origin": "테스트기관",
        "address": "서울 종로구 세종대로 1",
    }
    geo = {
        "테스트식당|테스트기관": {
            "lat": 37.0,
            "lon": 127.0,
            "match_mode": "address",
            "query": "경기 수원시 팔달구 1",
            "display_name": "경기 수원시 팔달구 1",
            "score": 100,
        }
    }
    key, row, meta = select_coordinate(record, geo)
    assert key is None and row is None, (key, row)
    assert any(x.get("reason") == "address_mismatch"
               for x in meta.get("rejected_candidates", [])), meta




def test_pdf_preamble_role_and_merged_date():
    rows = [
        ["2026년 2분기 업무추진비 집행내역(부의장)"],
        ["사용일자", "집행목적", "집행장소", "대상인원", "집행금액"],
        ["2026-04-03", "간담회", "테스트식당", 4, 120000],
        ["", "간담회", "다른식당", 3, 90000],
    ]
    meta = {
        "region": "경기",
        "jurisdiction": "테스트시",
        "institution": "테스트시의회",
        "source": "test",
        "post_url": "https://example.invalid/post",
        "attachment_url": "https://example.invalid/file",
        "attachment_name": "test.pdf",
        "period": [2026, None, 2],
        "default_role": "",
    }
    normalized, info = normalize_sheet(rows, "pdf-page-1", meta)
    assert len(normalized) == 2, normalized
    assert normalized[0]["role"] == "부의장", normalized[0]
    assert normalized[1]["role"] == "부의장", normalized[1]
    assert normalized[1]["used_date"] == "2026-04-03", normalized[1]
    assert normalized[1]["date_inferred_from_previous_row"] is True, normalized[1]
    assert info.get("section_role") == "부의장", info


def test_removed_selected_location_button():
    template = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
    map_js = (ROOT / "site" / "maplibre.js").read_text(encoding="utf-8")
    assert "selectedBtn" not in template
    assert "selectedBtn" not in map_js
    assert "선택 위치" not in template


def main():
    tests = [
        test_role_column_priority,
        test_role_from_purpose,
        test_national_name_only_coordinate_is_suppressed,
        test_address_mismatch_coordinate_is_suppressed,
        test_pdf_preamble_role_and_merged_date,
        test_removed_selected_location_button,
    ]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"regression checks passed: {len(tests)}")


if __name__ == "__main__":
    main()
