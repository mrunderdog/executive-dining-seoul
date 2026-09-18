# National legislator political-fund ingestion — 2024

> Source lineage: Central Election Commission accounting reports → information-disclosure PDFs → OhmyNews/Kyunghyang/Newstapa OCR/normalization → this project.

- Rows: **134,472**
- Workbooks: **2**
- Merchant keys with address metadata from detailed workbooks: **20,559**
- Legacy spending rows enriched with an address: **122,193**
- Errors: **0**

## Workbook diagnostics

- 21대 `2024_KAPF-21.xlsx`: parsed **63,820** / documented **64,391**
  - `Data` rows=73,032, cols=13, 2024-date=63,820, parsed=63,820
  - `설명` rows=4, cols=4, 2024-date=0, parsed=0
  - `지출내역분류기준` rows=52, cols=3, 2024-date=0, parsed=0
  - `의원정보` rows=812, cols=5, 2024-date=0, parsed=0
  - `정당코드` rows=45, cols=9, 2024-date=0, parsed=0
- 22대 `2024_KAPF-22.xlsx`: parsed **70,652** / documented **70,652**
  - `Data` rows=70,653, cols=11, 2024-date=70,652, parsed=70,652
  - `설명` rows=4, cols=4, 2024-date=0, parsed=0
  - `지출내역분류기준` rows=52, cols=3, 2024-date=0, parsed=0
  - `의원정보` rows=812, cols=5, 2024-date=0, parsed=0
  - `정당코드` rows=45, cols=9, 2024-date=0, parsed=0

## Detailed workbook address probe

- 21대 `2024_KAPF-21_수입지출.xlsx`
  - `Data`: OK / address rows=62,957 / cols=21
    - header row 1, merchant col 14, address col 16: ['총연번', '의원번호', '의원명', '당', '당ID', '지역명', '연월일', '내역', '수입금회', '수입누계', '지출금회', '지출누계', '잔액', '성명-법인단체명', '생년월일-사업자번호', '주소-사무소소재지', '직업-업종', '전화번호', '영수증일련번호', '분류', '']
  - `설명`: NO_MERCHANT_ADDRESS_HEADER / address rows=0 / cols=4
  - `지출내역분류기준`: NO_MERCHANT_ADDRESS_HEADER / address rows=0 / cols=3
  - `의원정보`: NO_MERCHANT_ADDRESS_HEADER / address rows=0 / cols=5
  - `정당코드`: NO_MERCHANT_ADDRESS_HEADER / address rows=0 / cols=9
- 22대 `2024_KAPF-22_수입지출.xlsx`
  - `Data`: OK / address rows=67,688 / cols=20
    - header row 1, merchant col 14, address col 16: ['연번', '의원번호', '의원명', '당', '당ID', '지역명', '연월일', '내역', '수입', '수입누계', '지출', '지출누계', '잔액', '성명', '사업자번호', '주소', '업종', '전화', '영수증', '분류']
  - `설명`: NO_MERCHANT_ADDRESS_HEADER / address rows=0 / cols=4
  - `지출내역분류기준`: NO_MERCHANT_ADDRESS_HEADER / address rows=0 / cols=3
  - `의원정보`: NO_MERCHANT_ADDRESS_HEADER / address rows=0 / cols=5
  - `정당코드`: NO_MERCHANT_ADDRESS_HEADER / address rows=0 / cols=9
