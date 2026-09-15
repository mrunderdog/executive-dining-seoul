# Monthly source status — 2026-08

Generated: 2026-09-15T17:28:42+09:00

## Summary

- **DISCOVERY_REQUIRED**: 24
- **TARGET_MONTH_VISIBLE**: 1

> This report is a source-discovery gate. A source being visible does **not** mean its PDF/XLSX rows were automatically ingested yet.
> Only district adapters that explicitly parse and normalize official expense rows may update `data/current.json`.

## Districts

| District | Status | Detail | Source |
|---|---|---|---|
| 강남구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 강동구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 강북구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 강서구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 관악구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 광진구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 구로구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 금천구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 노원구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 도봉구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 동대문구 | DISCOVERY_REQUIRED | seed period source had no public data | - |
| 동작구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 마포구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 서대문구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 서초구 | TARGET_MONTH_VISIBLE | HTTP 200; markers=2026년 8월,2026년8월,2026.08,2026-08,2026/08 | [official](https://www.sdc.seoul.kr/kr/news/bbsBusiness.do) |
| 성동구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 성북구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 송파구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 양천구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 영등포구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 용산구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 은평구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 종로구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 중구 | DISCOVERY_REQUIRED | official listing URL not verified | - |
| 중랑구 | DISCOVERY_REQUIRED | official listing URL not verified | - |

## Publish gate

- `TARGET_MONTH_VISIBLE` only means the official listing appears to contain the target month.
- Raw expense ingestion, entity matching, geocoding, scoring and manual review are separate gates.
- Do not publish a newly discovered restaurant without source lineage and a stable entity match.
