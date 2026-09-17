# Supplemental source status — 2026-08

> Supplemental cohorts are monitored separately from the 66 basic councils and are not directly comparable by default.

| Region | Institution | Cohort | Adapter | Status | Source |
|---|---|---|---|---|---|
| 서울 | 서울특별시 본청 | regional_executive | seoul_open_data_dataset | SOURCE_OK_TARGET_PERIOD_NOT_FOUND | [official](https://data.seoul.go.kr/dataList/OA-22156/S/1/datasetView.do) |
| 경기 | 경기도청 | regional_executive | gyeonggi_expense_boards | FETCH_FAILED | [official](https://www.gg.go.kr/bbs/board.do?bsIdx=803&menuId=1768) |
| 인천 | 인천광역시청 | regional_executive | discovery_required | DISCOVERY_REQUIRED | - |
| 국회 | 국회의원 | national_legislator | discovery_required | DISCOVERY_REQUIRED | - |

## Publication policy

- `TARGET_PERIOD_VISIBLE` is only a discovery signal.
- Each source requires a source-specific ingestion adapter and lineage-preserving normalization before publication.
- `national_legislator` records remain a separate cohort unless a later scoring policy explicitly bridges cohorts.
