#!/usr/bin/env python3
"""Small dependency-free regression suite for bugs already seen in production."""
from pathlib import Path

from coordinate_selection import select_coordinate
from build_source_candidates import plausible_transaction
from capital_backfill import Source, canonical_attachment_url, post_like, sanitize_discovered_posts, title_period
from repair_raw_dates import parse_date_text
from ingest_council_expense import infer_pdf_context_role, map_columns, normalize_sheet, recover_amount_from_row, recover_date_from_row, resolve_role, valid_transaction_merchant

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



def test_pdf_role_context_can_carry_across_pages():
    title_page = [
        ["2026년 2분기 시흥시의회"],
        ["부의장 업무추진비 집행내역"],
    ]
    table_page = [
        ["사용일자", "집행목적", "집행장소", "대상인원", "집행금액"],
        ["2026-04-03", "간담회", "테스트식당", 4, 120000],
    ]
    carried = infer_pdf_context_role(title_page)
    assert carried == "부의장", carried
    meta = {
        "region": "경기",
        "jurisdiction": "시흥시",
        "institution": "시흥시의회",
        "source": "siheung",
        "post_url": "https://example.invalid/post",
        "attachment_url": "https://example.invalid/file",
        "attachment_name": "test.pdf",
        "period": [2026, None, 2],
        "default_role": carried,
    }
    normalized, _ = normalize_sheet(table_page, "pdf-page-2", meta)
    assert normalized and normalized[0]["role"] == "부의장", normalized



def test_abbreviated_date_recovery():
    assert recover_date_from_row(["8.", "5.", "식당"], [2026, 8, None]) == "2026-08-05"
    assert recover_date_from_row(["8. 5.", "식당"], [2026, 8, None]) == "2026-08-05"
    assert recover_date_from_row(["5일", "식당"], [2026, 8, None]) == "2026-08-05"
    rows = [
        ["일시", "집행장소", "집행목적", "집행금액"],
        ["8. 5.", "테스트식당", "간담회 식비", 120000],
    ]
    meta = {
        "region":"인천","jurisdiction":"인천광역시","institution":"인천광역시의회",
        "source":"incheon_council","post_url":"x","attachment_url":"x","attachment_name":"x.pdf",
        "period":[2026,8,None],"default_role":"의장",
    }
    normalized, _ = normalize_sheet(rows, "pdf-page-1", meta)
    assert normalized and normalized[0]["used_date"] == "2026-08-05", normalized





def test_quarter_title_and_detail_routes():
    assert title_period("2026년 파주시의회 업무추진비 내역(1분기)") == (2026, None, 1)
    assert title_period("안산시의회 2026년도 2분기 업무추진비 집행내역 공개") == (2026, None, 2)

    paju = Source("paju", "경기", "파주시", "파주시의회", "https://example.invalid", 1, "quarterly")
    assert post_like({
        "text": "2026년 파주시의회 업무추진비 내역(2분기)",
        "url": "https://www.pajucouncil.go.kr/content/data/operatingExpense.html?fidx=21770&gtid=chujin&pg=vv",
    }, paju)

    icheon = Source("icheon", "경기", "이천시", "이천시의회", "https://example.invalid", 1, "monthly")
    assert post_like({
        "text": "이천시의회 의회운영업무추진비 집행내역(2026년 7월)",
        "url": "https://council.icheon.go.kr/content/information/businessOperatingExpense.html?fidx=5942&pg=vv",
    }, icheon)


def test_attachment_discovery_deduplication():
    assert canonical_attachment_url("https://x.test/attach") is None
    assert canonical_attachment_url("https://x.test/bbsAttachDownload.do") is None
    assert canonical_attachment_url("https://x.test/download.do?fileName=a.xlsx") == "https://x.test/download.do?fileName=a.xlsx"
    posts = [
        {"attachments": [
            {"url": "https://x.test/download.do?fileName=a.xlsx", "text": "a"},
            {"url": "https://x.test/fa fa-download text-warning", "text": "fake"},
        ]},
        {"attachments": [
            {"url": "https://x.test/download.do?fileName=a.xlsx", "text": "a again"},
            {"url": "https://x.test/download.do?fileName=b.xlsx", "text": "b"},
        ]},
    ]
    cleaned = sanitize_discovered_posts(posts)
    urls = [a["url"] for p in cleaned for a in p["attachments"]]
    assert urls == [
        "https://x.test/download.do?fileName=a.xlsx",
        "https://x.test/download.do?fileName=b.xlsx",
    ]


def test_shifted_amount_recovery():
    mapping = {"date": 0, "merchant": 1, "people": 3, "amount": 4}
    row = ["2026-08-05", "테스트식당", "간담회 식비", "5명", "5명", "125,000원", "카드"]
    assert recover_amount_from_row(row, mapping) == 125000
    noisy = ["2026-08-05", "테스트식당", "간담회", "5", "5명", "18", "카드"]
    assert recover_amount_from_row(noisy, mapping) is None


def test_implausible_amount_is_quarantined():
    assert plausible_transaction({"amount": 180000, "people": 8})
    assert not plausible_transaction({"amount": 18, "people": 8})
    assert plausible_transaction({"amount": 0, "people": 8})



def test_structural_merchant_rows_are_rejected():
    assert not valid_transaction_merchant("3828700")
    assert not valid_transaction_merchant("(단위 : 원)")
    assert not valid_transaction_merchant("인원 사용방법")
    assert valid_transaction_merchant("1973 산꼼장어")


def test_date_time_suffix_normalization():
    assert parse_date_text("25.11.18. 14:37").isoformat() == "2025-11-18"
    assert parse_date_text("25.11.24 19:54").isoformat() == "2025-11-24"



def test_two_row_header_parsing():
    rows = [
        ["사", "집", "사", "대", "금"],
        ["용일자", "행목적", "용처", "상인원", "액"],
        ["2026-08-05", "관계자 간담회 식비", "테스트식당", 4, 120000],
    ]
    meta = {
        "region":"경기","jurisdiction":"연천군","institution":"연천군의회",
        "source":"yeoncheon","post_url":"x","attachment_url":"x","attachment_name":"x.xlsx",
        "period":[2026,8,None],"default_role":"의장",
    }
    normalized, info = normalize_sheet(rows, "Sheet1", meta)
    assert info.get("header_span") == 2, info
    assert len(normalized) == 1, normalized
    assert normalized[0]["merchant"] == "테스트식당", normalized
    assert normalized[0]["amount"] == 120000, normalized


def test_removed_selected_location_button():
    template = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
    map_js = (ROOT / "site" / "maplibre.js").read_text(encoding="utf-8")
    assert "selectedBtn" not in template
    assert "selectedBtn" not in map_js
    assert "선택 위치" not in template



def test_template_has_no_legacy_leaflet_runtime():
    template = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
    build = (ROOT / "pipeline" / "build_site.py").read_text(encoding="utf-8")
    assert "leaflet.js" not in template.lower()
    assert "leaflet.css" not in template.lower()
    assert "L.map(" not in template
    assert "<!-- APP_RUNTIME -->" in template
    assert 'APP_JS = ROOT / "site" / "app.js"' in build
    assert 'APP_CSS = ROOT / "site" / "app.css"' in build


def main():
    tests = [
        test_role_column_priority,
        test_role_from_purpose,
        test_national_name_only_coordinate_is_suppressed,
        test_address_mismatch_coordinate_is_suppressed,
        test_pdf_preamble_role_and_merged_date,
        test_pdf_role_context_can_carry_across_pages,
        test_abbreviated_date_recovery,
        test_shifted_amount_recovery,
        test_attachment_discovery_deduplication,
        test_quarter_title_and_detail_routes,
        test_implausible_amount_is_quarantined,
        test_structural_merchant_rows_are_rejected,
        test_date_time_suffix_normalization,
        test_two_row_header_parsing,
        test_removed_selected_location_button,
        test_template_has_no_legacy_leaflet_runtime,
    ]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"regression checks passed: {len(tests)}")


if __name__ == "__main__":
    main()
