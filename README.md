# Executive Dining Seoul

서울 공공기관 업무추진비 공개자료에서 **단순히 많이 간 식당**이 아니라 `고위직 반복 선택(Executive Repeat)`과 `관외/원정 선택(Destination VIP)` 신호를 뽑아 지도에서 탐색하는 프로젝트입니다.

## 현재 상태

- UI: v5 지도 기반 정적 웹앱
- 초기 데이터: 2024-12 ~ 2025-04 서울 자치구의회 의장단 업무추진비 seed
- 공개 업소: 244곳
- canonical data: `data/current.json.gz.b64` (gzip+base64)
- 사이트 빌드: `pipeline/build_site.py`
- 품질검사: `pipeline/quality_gate.py`
- 월간 실행: 매월 15일 12:00 KST

> 월간 workflow는 **review-before-publish** 방식입니다. 자동 식별이 확실하지 않은 업소는 본 데이터에 조용히 합치지 않습니다. 현재 V1은 배포/품질검사/source monitoring/PR 생성 골격을 먼저 고정했고, 25개 자치구별 ingestion adapter는 순차 활성화합니다.

## 데이터 원칙

1. 원자료와 업체정보를 분리합니다.
2. 직책/사용일/장소/금액/인원/집행목적을 가능한 한 원자료에서 유지합니다.
3. 업체명만 같은 경우 자동 병합하지 않습니다. 주소/지점/출발기관을 함께 봅니다.
4. 미확인 업종·주소를 임의 확정하지 않습니다.
5. quality gate를 통과한 변경만 월간 PR로 제안합니다.
6. 사람이 PR을 확인해 merge해야 공개 사이트가 갱신됩니다.

## 구조

```text
site/template.html             # 지도 UI
data/current.json.gz.b64       # canonical dataset
sources/registry.json          # source registry
pipeline/data_io.py            # dataset codec
pipeline/build_site.py         # template -> index.html
pipeline/quality_gate.py       # 데이터 품질검사
pipeline/monthly_update.py     # 월간 source status/report
.github/workflows/pages.yml     # GitHub Pages 배포
.github/workflows/monthly.yml   # 월간 review PR
```

## 로컬 실행

```bash
python pipeline/quality_gate.py
python pipeline/build_site.py
# 배포 artifact와 같은 plain JSON을 만들고 싶다면 data_io.py를 사용
python -m http.server 8000
```

`index.html`은 `file://`로 직접 열지 말고 HTTP server에서 확인합니다.

## GitHub Pages

Repository **Settings → Pages → Build and deployment → Source: GitHub Actions** 를 한 번 선택합니다. 이후 `main` push마다 `pages.yml`이 quality gate → site build → dataset decode → Pages deploy를 수행합니다.

예상 URL: `https://mrunderdog.github.io/executive-dining-seoul/`

## 월간 업데이트

- 매월 15일 12:00 KST
- 직전월을 target month로 사용
- source 상태와 데이터 품질을 검사
- 변경사항이 있으면 `bot/monthly-YYYY-MM` branch와 PR 생성
- merge 후 Pages 자동 배포

### 아직 남은 핵심 작업

월 1회 **실제 신규 지출내역까지 완전 자동 반영**하려면 각 구의회/구청의 서로 다른 PDF/XLSX/게시판 형식을 읽는 source adapter가 필요합니다. V1에서는 잘못된 식당/지점 매칭을 피하기 위해 이 부분을 억지로 자동화하지 않았습니다.

## Scoring

점수는 맛 평점이 아니라 선택 패턴 탐색용입니다.

- **Destination VIP**: 관외 강도, 반복 방문, 의장/부의장 방문, 직책 다양성, 지속성, 저녁 비중
- **Executive Repeat**: 의장/부의장 반복 선택, 직책 다양성, 지속성, 기관 다양성, 저녁 비중
