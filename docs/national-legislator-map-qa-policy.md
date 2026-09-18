# National Legislator Map QA Policy

Updated: 2026-09-18

## Purpose

The National Assembly cohort is derived from 2024 political-fund spending records. Restaurant ranking and map publication are separate stages: a merchant can rank as a dining candidate without being safe to place on the public map.

## Publication gate

- **A** — source merchant has an address and that address is geocoded, or merchant + source address agree. Auto-publish.
- **B** — strong address-based geocoder match. Auto-publish.
- **C** — name-only match without a source address. Review only; do not publish automatically.
- **D** — missing or ambiguous coordinate. Do not publish.
- **F** — non-restaurant merchant/category veto. Do not publish.

The public National Assembly list contains up to 80 highest-ranked **A/B** candidates, selected from the top 200 dining candidates. The pipeline fails if fewer than 50 candidates pass QA.

## Current QA result

- Candidates reviewed: **200**
- A: **198**
- D: **2**
- Publicly approved: **80 / 80**
- Gate: **PASS**

The two unresolved candidates in this run were `여운관` and `더센다이`; both remain outside the public map until their location can be resolved safely.

## Data-quality fixes applied

1. Reject non-positive/adjustment rows and obvious non-dining merchants.
2. Exclude party/financial/rental/printing/cafe/hotel/canteen/catering-company noise from restaurant publication.
3. Keep source merchant addresses from the detailed 2024 workbooks.
4. Resolve branch entities with address-aware keys rather than merchant name alone.
5. Geocode up to 200 candidates before selecting the public top 80.
6. Publish only QA-approved A/B entities.
7. Require every published National Assembly record to have a static coordinate.
8. Serialize data-writing GitHub Actions to prevent geocode-cache merge conflicts.

Generated evidence is stored in:

- `reports/national-legislator-map-qa.json`
- `reports/national-legislator-map-qa.md`
- `reports/national-legislator-candidates.json`
