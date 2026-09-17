# Capital Region Expansion

## Scope

Executive Dining expands from Seoul basic local councils to a broader public-sector dining intelligence dataset.

### Core comparable universe (P0)

- Seoul: 25 basic local councils
- Gyeonggi: 31 basic local councils
- Incheon: 10 basic local councils

Total: **66 basic local councils**.

### Regional legislatures (P0.5)

- Seoul Metropolitan Council
- Gyeonggi Provincial Council
- Incheon Metropolitan Council

These are stored separately as `regional_council` because their geography and spending patterns are not directly comparable with basic councils.

### Regional executive governments (P1)

- Seoul Metropolitan Government / Seoul City Hall
- Gyeonggi Provincial Government
- Incheon Metropolitan Government

These use `jurisdiction_level=regional_executive` and `source_family=executive_government`. Mayor/governor offices and senior-department spending are especially valuable Executive Dining signals, but should be scored within an executive-government cohort rather than mixed directly into local-council rankings.

### National legislators (P1.5)

- Members of the National Assembly, only where an official disclosure source exposes merchant-level spending with sufficient date, amount, purpose and source lineage.

These use `jurisdiction_level=national_legislator` and `source_family=legislator_public_spending`. Political-fund or parliamentary spending is not assumed to be directly comparable with local-government business-promotion expenses, so it remains a separate cohort by default.

## Canonical jurisdiction fields

Newly ingested rows should carry:

- `region`: `서울`, `경기`, `인천`, or `국회`
- `jurisdiction`: canonical display name
- `jurisdiction_level`: `basic_council`, `regional_council`, `regional_executive`, or `national_legislator`
- `institution`: official institution name
- `source_family`: `council_leadership`, `executive_government`, or `legislator_public_spending`
- `cohort`: comparison cohort used by ranking and UI filters

Legacy Seoul seed records may still contain only `origin` such as `중랑구`; UI and normalization code should treat those as Seoul basic-council records until migrated.

## Collection policy

1. Official council / government / statutory disclosure source only for canonical expense rows.
2. Search engines and third-party sites are source-discovery aids, never canonical expense evidence.
3. Source discovery does not equal ingestion.
4. New attachment/API formats receive an explicit adapter before publication.
5. PDF/HWP/XLS/XLSX/API rows are normalized into one event schema before entity matching.
6. Restaurant matching requires stable evidence; same merchant name alone is insufficient when branch ambiguity exists.
7. Source lineage must remain attached to every published event.
8. Cross-cohort comparisons are opt-in. Local councils, regional legislatures, regional executives and national legislators are separate by default.

## Rollout

### Phase A — source registry

Register all 66 basic councils, 3 regional councils and supplemental executive/legislator source families. Mark only manually verified official disclosure surfaces as verified.

### Phase B — high-yield adapters

Prioritize sources that expose structured XLS/XLSX/API data or predictable monthly/quarterly boards. Current priorities are Goyang/Suwon-style council spreadsheets, Seoul City Hall Open Data and Gyeonggi Provincial Government disclosure boards.

### Phase C — backfill

Backfill from the current seed start date (2024-12) where the official archive permits it. Preserve publication cadence separately from event date.

### Phase D — scoring

Recalculate Destination VIP using exact origin geography so that cross-Seoul/Gyeonggi/Incheon movement is meaningful. Add institution diversity and cross-jurisdiction consensus signals while keeping comparison cohorts separate by default.

## Why the expansion matters

The Seoul-only model cannot distinguish whether a restaurant is merely near a council office or repeatedly selected by senior officials from multiple independent institutions. Capital-region and executive-level coverage enables a stronger signal: **cross-jurisdiction and cross-institution consensus** — the same restaurant independently selected by senior public officials from different institutions.
