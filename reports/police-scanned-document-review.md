# 경찰청 치안정보국장 이미지형 PDF 거래별 검증 — 2026-10-12

공식 PDF 원본은 GitHub Actions [run #38193884660](https://github.com/mrunderdog/executive-dining-seoul/actions/runs/38193884660/artifacts/11722388475)의 SHA-256 증빙 파일이며, PDF 텍스트 레이어가 없는 이미지형 자료입니다. 각 페이지를 렌더링하여 **원문에 기재된 사용자·일자·사용처·금액·대상인원**을 직접 판독했고 월별 소계와 재합산했습니다. 이 자료는 공식 **집행 명의**에 대한 증거이며 해당 고위직의 실제 참석을 증명하지 않습니다.

| 대상 | SHA-256 | 거래 건수 | 원문 소계 | 재합산 | QA |
|---|---|---:|---:|---:|---|
| 2026-05 | `1139d2be05e073fe6f44c9a7666b23bae26e306d21fbcd7daaa9d6e13f07b08b` | 5 | 883,000 | 883,000 | 일치 |
| 2026-06 | `c22920bba55108f288f36c2636e0d98faface0fd1c18c2ded9ec8c184256279a` | 8 | 1,449,960 | 1,449,960 | 일치 |
| 2026-07 | `172baf2349b9315e866ca530623cfe23106d34fc5a1273cb61f3a550dc66f134` | 4 | 708,300 | 708,300 | 일치 |
| **합계** | | **17** | **3,041,260** | **3,041,260** | **일치** |

추가된 17건은 `data/raw/police_expense_staging.json`에 `STAGING_ONLY`, `NOT_ESTABLISHED`, `HUMAN_VISUAL_REVIEW_OF_OFFICIAL_PDF` 표시와 원본 SHA·공식 첨부 URL·문서별 행 번호를 붙였습니다. 기존 텍스트형 PDF에서 검증한 26건은 그대로 유지되며 전체 **43건**입니다.

**지도 공개 제한:** 식당명만으로는 업소 실체 또는 거래 당시 개별 지점 주소를 알 수 없습니다. 특히 동명 음식점, 법인 결제처, 체인점은 위치 근거 없이 지도에 노출하지 않으며, 원문 '사용자'는 실제 식사 참석자로 환산하지 않습니다. 스캔 PDF 행별 육안 판독이므로 추후 별도 검토자가 원본 행을 재확인할 수 있도록 SHA·행 위치를 보존합니다.

**원문 상세 페이지:** [2026년 5·6월](https://www.police.go.kr/user/bbs/BD_selectBbs.do?q_bbsCode=1025&q_bbscttSn=20260720141942652), [2026년 7월](https://www.police.go.kr/user/bbs/BD_selectBbs.do?q_bbsCode=1025&q_bbscttSn=20260811095601067).
