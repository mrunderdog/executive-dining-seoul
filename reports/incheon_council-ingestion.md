# incheon_council expense ingestion

- Normalized rows: **194**
- Source posts: **20**
- Refresh mode: **full**
- Files retained: **10**
- New files downloaded: **10**
- Errors: **3**

## Rows by year

- 2026: 188

## Top roles / sheets

- 부의장: 108
- 의장: 71
- 예산결산특별위원장: 9
- 행정안전위원장: 6

## Files

- `첨부파일 다운로드 xlsx 2026년_7월~9월_업무추진비_공개_의장.xlsx` — 19,881 bytes — 71 rows
  - 의장(3분기): OK / parsed 71 / mapping {'date': 0, 'merchant': 2, 'people': 3, 'amount': 6, 'method': 7}
- `첨부파일 다운로드 xlsx 부의장실_업무추진비_집행내역(7~9월,_제1부).xlsx` — 19,445 bytes — 72 rows
  - 7월: OK / parsed 24 / mapping {'date': 0, 'merchant': 2, 'people': 3, 'amount': 6, 'method': 7}
  - 8월: OK / parsed 32 / mapping {'date': 0, 'merchant': 2, 'people': 3, 'amount': 6, 'method': 7}
  - 9월: OK / parsed 16 / mapping {'date': 0, 'merchant': 2, 'people': 3, 'amount': 6, 'method': 7}
- `첨부파일 다운로드 xlsx 부의장실_업무추진비_집행내역(7~9월,_제2부).xlsx` — 16,710 bytes — 36 rows
  - 7월: OK / parsed 16 / mapping {'date': 0, 'merchant': 2, 'people': 3, 'amount': 6, 'method': 7}
  - 8월: OK / parsed 8 / mapping {'date': 0, 'merchant': 2, 'people': 3, 'amount': 6, 'method': 7}
  - 9월: OK / parsed 12 / mapping {'date': 0, 'merchant': 2, 'people': 3, 'amount': 6, 'method': 7}
- `(2026년 9월 환경교통위원장 업무추진비 집행내역 ) 첨부파일 다운받기` — 90,059 bytes — 0 rows
  - pdf-page-1: NO_HEADER / parsed 0 / mapping {}
- `(2026년 9월 의회운영위원장 업무추진비 집행내역) 첨부파일 다운받기` — 49,844 bytes — 0 rows
  - pdf-page-1: NO_HEADER / parsed 0 / mapping {}
- `(2026년 9월 예산결산특별위원장 업무추진비 집행내역) 첨부파일 다운받기` — 76,412 bytes — 9 rows
  - pdf-page-1: OK / parsed 9 / mapping {'date': 0, 'merchant': 1, 'purpose': 2, 'people': 3, 'amount': 4, 'method': 5}
- `(2026년 9월 행정안전위원장 업무추진비 집행내역) 첨부파일 다운받기` — 43,802 bytes — 6 rows
  - pdf-page-1: OK / parsed 6 / mapping {'date': 0, 'merchant': 1, 'purpose': 2, 'people': 5, 'amount': 6, 'method': 7}
- `(2026년 9월 교육위원장 업무추진비 집행내역) 첨부파일 다운받기` — 67,452 bytes — 0 rows
  - pdf-page-1: NO_HEADER / parsed 0 / mapping {}
- `(2026년 9월 도시건설위원장 업무추진비 집행내역) 첨부파일 다운받기` — 59,557 bytes — 0 rows
  - pdf-page-1: NO_HEADER / parsed 0 / mapping {}
- `첨부파일 다운로드 pdf 2026년_8월_환경교통위원장_업무추진비_집행내역_.pdf` — 69,457 bytes — 0 rows
  - pdf-page-1: NO_HEADER / parsed 0 / mapping {}
  - pdf-page-2: NO_HEADER / parsed 0 / mapping {}

## Errors

- ValueError: PDF contained no extractable text rows — https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&fileno=1&msg_seq=1329
- KeyError: "There is no item named '[Content_Types].xml' in the archive" — https://www.icouncil.go.kr/main/bbs/bbsMsgFileDownCompress.do?bcd=infordisc&msg_seq=1328
- ValueError: PDF contained no extractable text rows — https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&fileno=1&msg_seq=1321
