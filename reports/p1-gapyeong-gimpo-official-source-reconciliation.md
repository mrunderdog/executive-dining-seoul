# P1 Official Source Reconciliation — Gapyeong and Gimpo (2026-10-30)

**Status: STRICT QA HOLD — neither agency's new transaction rows are approved for publication.**

## Gimpo — seven live verified XLSX files

The full, original-source reconciliation accounts for all **1,819 parsed expense rows**:

| Disposition | Rows | Decision |
|---|---:|---|
| Valid merchant/date/amount/provenance | 1,793 | Candidate rows; overall source HOLD |
| Identical September 2025 expenses repeated in Q4, with verified exact Q3 matches | 17 | Cross-file duplicates; do not double-count |
| Cash wedding, condolence, staff-support payments with no place | 7 | Genuine non-dining spending; retain separate ledger |
| April 6, 2026 expense appearing in official Q1 sheet | 1 | HOLD_SOURCE_PERIOD |
| August 8, 2025 card expense with blank merchant/purpose | 1 | HOLD_UNIDENTIFIED_PLACE |
| **Total** | **1,819** | Every parsed row explicitly accounted for |

The 17 cross-quarter duplicates are matched against actual Q3 document transactions
on date/time, payer role, merchant, purpose, amount, attendees, payment method.
The 7 cash-support rows are never converted into dining venues. The eighth
blank-merchant row is a card payment, so it **remains unidentified**.

### Exact unresolved official evidence

**2026 Q1/April date:** [Official Gimpo post 748294](https://gimpocouncil.go.kr/cnts/bbs/infoView.php?bbsCd=act&bbsSubCd=act0702&bbsSn=748294);
attachment FileDownLoad flSn 18771, sheet 도시환경, original row 6:
2026-04-06, 카페모임, KRW 13,400. No exact match found in the Q2 workbook.
Do not alter the official date or reassign the document quarter without evidence.

**Unidentified place:** [Official Gimpo post 747842](https://gimpocouncil.go.kr/cnts/bbs/infoView.php?bbsCd=act&bbsSubCd=act0702&bbsSn=747842);
attachment flSn 18323, sheet 부의장, original row 56:
2025-08-08, KRW 54,800 by card; place and purpose blank.
Do not invent a restaurant.

The new source-specific reconciliation ledger preserves original records and
their original file URLs; strict QA verifies ledger completeness and exact-match
duplicate evidence. It **rejects both unresolved HOLD items**.

## Gapyeong — five official PDFs

SHA-256 checked official PDF bytes yield **370 parsed rows**, up from 348:
2024 Q4 = 103; 2025 Q1 = 79; 2025 Q4 = 68; 2026 Q1 = 73; 2026 Q2 = 47.
The 2024 Q4 document contains September transactions, which remain dated
September; there is no fictional date or quarter adjustment.

Seven transaction-like PDF rows remain unparsed and explicitly marked
ROW_PARSE_GAPS: one in the 2026 Q1 PDF and six in 2025 Q4.
The source remains strictly HOLD because of this and quarter mismatches.
When the official listing times out, collection fails closed.

[SHA-verified official-PDF audit](https://github.com/mrunderdog/executive-dining-seoul/actions/runs/40987753465).

## Production gate

Keep both sources out of the published raw datasets until full original-source
QA passes, with no unresolved row, incomplete discovery or forged metadata.
Require existing data/file immutability, ranking/entity QA and Pages smoke tests.
No prior data or QA threshold was deleted or weakened.

[PR #168](https://github.com/mrunderdog/executive-dining-seoul/pull/168)
and [Issue #167](https://github.com/mrunderdog/executive-dining-seoul/issues/167).
