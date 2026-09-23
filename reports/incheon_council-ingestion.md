# incheon_council expense ingestion

- Normalized rows: **19**
- Source posts: **20**
- Downloaded files: **7**
- Errors: **3**

## Rows by year

- 2026: 19

## Top roles / sheets

- 예산결산특별위원장: 10
- 행정안전위원장: 9

## Files

- `첨부파일 다운로드 pdf 2026년_8월_환경교통위원장_업무추진비_집행내역_.pdf` — 69,457 bytes — 0 rows
  - pdf-page-1: NO_HEADER / parsed 0 / mapping {}
  - pdf-page-2: NO_HEADER / parsed 0 / mapping {}
- `첨부파일 다운로드 pdf 2026년_8월_의회운영위원장_업무추진비_집행내역.pdf` — 52,621 bytes — 0 rows
  - pdf-page-1: NO_HEADER / parsed 0 / mapping {}
- `첨부파일 다운로드 pdf 2026년_8월_행정안전위원장_업무추진비_집행내역.pdf` — 46,189 bytes — 9 rows
  - pdf-page-1: OK / parsed 9 / mapping {'date': 0, 'merchant': 1, 'purpose': 2, 'people': 5, 'amount': 6, 'method': 7}
- `(2026년 8월 예산결산특별위원장 업무추진비 집행내역) 첨부파일 다운받기` — 55,119 bytes — 10 rows
  - pdf-page-1: OK / parsed 10 / mapping {'date': 0, 'merchant': 1, 'purpose': 2, 'people': 3, 'amount': 4, 'method': 5}
- `(2026년 8월 도시건설위원장 업무추진비 집행내역) 첨부파일 다운받기` — 54,305 bytes — 0 rows
  - pdf-page-1: NO_HEADER / parsed 0 / mapping {}
- `( 2026년 7월 산업경제위원장 업무추진비 집행내역 ) 첨부파일 다운받기` — 88,744 bytes — 0 rows
  - pdf-page-1: NO_HEADER / parsed 0 / mapping {}
- `(2026년 7월 환경교통위원장 업무추진비 집행내역 ) 첨부파일 다운받기` — 68,085 bytes — 0 rows
  - pdf-page-1: NO_HEADER / parsed 0 / mapping {}
  - pdf-page-2: NO_HEADER / parsed 0 / mapping {}

## Errors

- ValueError: PDF contained no extractable text rows — https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&fileno=1&msg_seq=1321
- URLError: <urlopen error timed out> — https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&fileno=1&msg_seq=1317
- URLError: <urlopen error timed out> — https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&fileno=1&msg_seq=1314
