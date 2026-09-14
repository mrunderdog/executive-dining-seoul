# Executive Dining Seoul

서울 공공기관 업무추진비 공개자료에서 **단순히 많이 간 식당**이 아니라,
`고위직 반복 선택(Executive Repeat)`과 `관외/원정 선택(Destination VIP)` 신호를 뽑아 지도에서 탐색하는 프로젝트입니다.

## 현재 상태

- UI: `v5` 지도 기준으로 배포 가능
- 초기 데이터: 2024-12 ~ 2025-04 서울 자치구의회 의장단 업무추진비 seed
- 고유 업소: 244곳
- 데이터 원본: `data/current.json`
- 사이트 생성: `pipeline/build_site.py`
- 품질검사: `pipeline/quality_gate.py`
- 월간 실행: 매월 15일 12:00 KST, 직전월 공개자료 상태 점검 후 PR 생성

> 현재 월간 자동화는 **배포/품질검사/공식 source discovery/PR 생성까지 자동화**되어 있습니다.
> 각 구의회가 PDF/XLSX/게시판 등 서로 다른 형식으로 공개하기 때문에, 실제 신규 지출건 ingestion adapter는 source별로 순차 확장합니다. 자동 식별이 확실하지 않은 자료는 곧바로 본 데이터에 합치지 않습니다.

## 데이터 원칙

1. 원자료와 업체정보를 분리한다.
2. 직책/사용일/장소/금액/인원/집행목적을 가능한 한 원자료에서 유지한다.
3. 업체명만 같은 경우 자동 병합하지 않는다. 주소/지점/출발기관을 함께 본다.
4. 미확인 업종·주소를 임의 확정하지 않는다.
5. 월간 업데이트는 quality gate를 통과한 변경만 PR로 제안한다.
6. 사람이 PR을 확인해 merge해야 공개 사이트가 갱신된다.

## 저장소 구조

```text
index.html                    # 배포되는 완성 페이지
site/template.html            # DATA/STATS/ORIGINS 주입용 템플릿
data/current.json             # 사이트의 canonical 데이터
sources/registry.json         # 공식 공개 source registry
pipeline/build_site.py        # current.json -> index.html
pipeline/quality_gate.py       # 데이터 품질 검사
pipeline/monthly_update.py     # 월간 source discovery/report
reports/                      # 월별 source 상태/갱신 보고서
.github/workflows/pages.yml    # GitHub Pages 배포
.github/workflows/monthly.yml  # 월간 업데이트 PR
```

## 로컬 빌드

```bash
python pipeline/quality_gate.py
python pipeline/build_site.py
python -m http.server 8000
```

브라우저에서 `http://localhost:8000`을 엽니다.

## 배포

GitHub repository **Settings → Pages → Build and deployment → Source = GitHub Actions** 로 한 번 설정하면,
`main`에 push될 때 Pages workflow가 `index.html`을 배포합니다.

## 월간 업데이트 정책

- 실행: 매월 15일 12:00 KST
- 대상: 직전월 공개자료
- 동작:
  1. 공식 source 게시 여부 확인
  2. source discovery report 생성
  3. 데이터/품질검사 수행
  4. 변경이 있으면 `bot/monthly-YYYY-MM` branch + PR 생성
  5. PR 검토 후 merge 시 사이트 자동 배포

공식 자료가 늦게 올라온 경우 다음 달 실행에서 다시 잡습니다.

## Scoring

점수는 맛 평점이 아니라 **선택 패턴을 찾기 위한 탐색 점수**입니다.

- Destination VIP: 관외 강도, 반복 방문, 의장/부의장 방문, 직책 다양성, 지속성, 저녁 비중
- Executive Repeat: 의장/부의장 반복 선택, 직책 다양성, 지속성, 기관 다양성, 저녁 비중
