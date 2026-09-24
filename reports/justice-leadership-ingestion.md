# Justice leadership expense ingestion

- Rows: **809**
- Merchant rows: **158**
- Files: **145**
- Errors: **6**

## Rows by institution

- 대검찰청: 141
- 법제처: 135
- 전주지방검찰청: 118
- 창원지방검찰청: 81
- 대구지방검찰청: 71
- 부산지방검찰청: 45
- 서울중앙지방검찰청: 44
- 대구고등검찰청: 29
- 법무부: 24
- 대전지방검찰청: 19
- 부산고등검찰청: 16
- 춘천지방검찰청: 15
- 청주지방검찰청: 15
- 광주지방검찰청: 14
- 제주지방검찰청: 12
- 서울북부지방검찰청: 10
- 서울남부지방검찰청: 8
- 서울서부지방검찰청: 7
- 서울동부지방검찰청: 4
- 울산지방검찰청: 1

## Rows by domain

- prosecution: 650
- legal_administration: 159

## Errors

- 법무부 / ministry_justice: ValueError: PDF contained no extractable text rows — https://www.moj.go.kr/bbs/moj/98/498016/download.do
- 법무부 / ministry_justice: RemoteDisconnected: Remote end closed connection without response — https://www.moj.go.kr/bbs/moj/98/497693/download.do
- 법무부 / ministry_justice: RemoteDisconnected: Remote end closed connection without response — https://www.moj.go.kr/bbs/moj/98/497692/download.do
- 광주고등검찰청 / prosecution_high_gwangju: ValueError: PDF contained no extractable text rows — https://www.spo.go.kr/cmm/fms/FileDown.do?atchFileId=FILE_000000000635176&fileSn=0
- 서울남부지방검찰청 / prosecution_district_southseoul: ValueError: PDF contained no extractable text rows — https://www.spo.go.kr/cmm/fms/FileDown.do?atchFileId=FILE_000000000633503&fileSn=0
- 춘천지방검찰청 / prosecution_district_chuncheon: ValueError: PDF contained no extractable text rows — https://www.spo.go.kr/cmm/fms/FileDown.do?atchFileId=FILE_000000000632255&fileSn=0
