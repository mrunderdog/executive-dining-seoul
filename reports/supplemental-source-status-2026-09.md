# Supplemental source status — 2026-09

> Supplemental cohorts are monitored separately from the 67 current basic councils and are not directly comparable by default.

| Region | Institution | Cohort | Discovery | Ingestion | Publication | Source |
|---|---|---|---|---|---|---|
| 서울 | 서울특별시 본청 | regional_executive | SOURCE_OK_TARGET_PERIOD_NOT_FOUND | IMPLEMENTED | PUBLISHED | [official](https://data.seoul.go.kr/dataList/OA-22156/S/1/datasetView.do) |
| 경기 | 경기도청 | regional_executive | FETCH_FAILED | IMPLEMENTED | PUBLISHED | [official](https://www.gg.go.kr/bbs/board.do?bsIdx=803&menuId=1768) |
| 인천 | 인천광역시청 | regional_executive | TARGET_PERIOD_VISIBLE | IMPLEMENTED | PUBLISHED | [official](https://www.incheon.go.kr/open/OPEN010301) |
| 국회 | 국회의원 | national_legislator | DISCOVERY_REQUIRED | IMPLEMENTED_SEPARATE_2024_DATASET | PUBLISHED_HISTORICAL_2024 | - |

## Status semantics

- `discovery_status`: official recurring disclosure surface visibility only.
- `ingestion_status`: whether a maintained parser/adapter exists.
- `publication_status`: whether normalized records are actually included in the public site.
- National Assembly 2024 political-fund records remain a separate historical cohort and are not the same as a current official recurring disclosure feed.
