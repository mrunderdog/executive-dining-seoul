# Executive Dining 수도권

공공기관의 **공식 업무추진비·공개 지출자료**에서 식당 선택 패턴을 정규화해 탐색하는 지도 프로젝트입니다. 식당의 맛을 평가하거나 공직자를 평가하는 서비스가 아니라, 반복 선택·기관 간 교차 선택·고위직 사용·관외 이동 같은 **공개 지출의 선택 신호**를 식당 단위로 보여줍니다.

## 현재 범위

- 수도권 기초의회: 서울·경기·인천
- 광역의회: 경기도의회·인천광역시의회 등 공식 소스가 검증된 범위
- 광역 집행부: 서울시청·경기도청·인천시청
- 중앙정부: 국무총리·부총리·장관·차관·기관장·실국장급 공개 업무추진비
- 국회의원: 공개 가능한 과거 지출자료를 별도 historical cohort로 관리

기관별 공개 방식이 달라 **지원됨 / 마지막 정상자료 유지(STALE_OK) / 탐색 필요** 상태를 구분합니다. 일시적인 공식 사이트 장애나 파서 실패가 정상 데이터를 0건으로 덮어쓰지 않도록 last-good 보존 정책을 사용합니다.

## 핵심 신호

- **Executive Repeat**: 동일 기관·고위직에서 반복 선택되는 식당
- **Destination VIP**: 관외·원정 선택이 반복되는 식당
- **Cross-Institution Consensus**: 서로 다른 기관이 독립적으로 선택한 동일 물리 식당
- **Top Official**: 중앙정부 총리·부총리·장관·차관급 공개분에서 확인되는 식당
- **Regional Executive**: 시장·부시장 등 광역 집행부 공개분에서 확인되는 식당

공직자·정당·기관 자체에는 점수나 순위를 부여하지 않습니다. 점수는 오직 식당 선택 패턴의 탐색 우선순위를 위한 값입니다.

## 데이터 모델

동일 식당 병합은 보수적으로 처리합니다. 기본적으로 **정규화된 상호 + 주소**가 일치해야 전역 식당 entity로 병합하며, 주소가 없는 동명이 식당은 기관 간 자동 병합하지 않습니다.

```text
official sources
  -> discovery
  -> raw ingestion
  -> date/schema QA
  -> source-level candidates
  -> publication gates
  -> global restaurant entity merge
  -> cross-institution / top-official signals
  -> static geocode cache
  -> MapLibre site
```

주요 파일:

```text
sources/registry.json                     # 수도권 의회 source registry
sources/central_executive_registry.json   # 중앙정부 source registry
pipeline/capital_backfill.py              # 수도권 의회 discovery
pipeline/ingest_council_expense.py        # 의회 원자료 정규화
pipeline/global_entities.py               # 전역 식당 entity + 교차기관 신호
pipeline/build_signal_reports.py          # 교차기관/장차관/광역집행부 QA
pipeline/build_site.py                    # 정적 사이트 생성
pipeline/quality_gate.py                  # 공개 데이터 품질검사
reports/signal-intelligence.md            # 신호 QA 요약
```

## 자동 갱신

- 수도권 의회: 지원 가능한 공식 게시판을 개별적으로 갱신
- 중앙정부: 공식 업무추진비 공개면에서 다운로드 가능한 자료를 정규화
- 광역 집행부: 서울·경기·인천을 별도 cohort로 수집
- 신호 QA: 원자료/후보 갱신 후 교차기관·장차관급 신호 리포트를 재생성
- 사이트: quality gate 통과 후 GitHub Pages 배포

공식 사이트가 일시적으로 응답하지 않거나 0건을 반환하면 기존 정상 데이터는 유지하고 상태만 stale로 처리합니다.

## 로컬 검증

```bash
python pipeline/quality_gate.py
python pipeline/build_signal_reports.py
python pipeline/build_site.py --output /tmp/index.html
```

## GitHub Pages

`main`의 검증된 데이터로 GitHub Actions가 정적 사이트를 빌드·배포합니다.

예상 URL: https://mrunderdog.github.io/executive-dining-seoul/
