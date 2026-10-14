# 업무추진비 증빙 의미 / 무료 식당 인허가 검증 (2026-10-14)

## P0: 보수적 증빙 분류
- 기존 `evidence.visits`는 과거 각 기관의 공개 거래/사용처 발생 횟수를 담는 **레거시 집계 필드**입니다. 변경 전에 원자료와 점수 및 기존 서비스 소비자를 보호하려고 유지합니다.
- 게시되는 모든 레코드는 `evidence_semantics.reported_usage_events`, `disclosed_spending_events`, `confirmed_person_attendances`, `personal_attendance_status`를 가집니다.
- 방문·사용처 공개 문서만으로 특정 공직자 개인의 실제 참석은 입증할 수 없습니다. 현재 `confirmed_person_attendances=0`이며 해당 근거를 얻기 전에는 임의 증가하지 않습니다.
- 경찰청은 이미 `spending_events`를 별도 저장하고, 공식 집행 명의자와 실제 참석을 분리합니다.
- **범위**: 현재 조치는 분류/표기 계층입니다. 레거시 순위 수치·행 자체를 대규모 변경하거나 일괄 '실제 방문'으로 재해석하지 않습니다. 전 기관 간 교차 점수도 보수적으로 재검토해야 합니다.

## P1: 무료 공식 인허가 원자료 매칭
출처: [행정안전부 전국일반음식점표준데이터](https://www.data.go.kr/data/15096283/standard.do)
(기관 다운로드 주소: https://file.localdata.go.kr/file/general_restaurants/info)

```bash
PYTHONPATH=pipeline python -m unittest -v test_evidence_semantics
python pipeline/audit_restaurant_licenses.py --input /path/to/official_general_restaurants.csv --output reports/restaurant-license-audit.json
```

실행환경은 현재 공공 원본 서버 DNS에 접근할 수 없어 전체 공식 CSV 확보/검증을 수행하지 못했습니다. 위 명령은 **정부가 배포한 CSV를 확보한 후** 실행합니다. GitHub Actions에 경로 없는 파일을 가정하거나 검증 결과를 만들어내지 않습니다. 기본 정책은 정확한 정규화 상호+전체 주소 1건 매칭만 인허가 일치로 표시하며 복수면 보류합니다. 결과에는 카드 결제 가맹점 인증/공직자 참석을 `false`로 고정합니다. 인허가 영업상태는 기준 시점과 추후 폐업 여부가 다를 수 있습니다.

## P2: 경찰청 정보공개청구 시범 (미제출)
- [청구문 초안](police-information-disclosure-request-draft-20261014.md)
- [원문 거래 12건](police-information-disclosure-12-transactions-20261014.csv)
- 경찰청에 사용처 소재지/사업자 가맹점 식별정보의 부분 공개 요청. 개인 카드번호·개인정보 등 불필요한 식별자는 제외. 실제 청구는 사용자 명의 및 인증 후 제출해야 합니다.
