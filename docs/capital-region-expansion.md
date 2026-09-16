# Capital Region Expansion

## Scope

Executive Dining expands from Seoul basic local councils to the full Seoul Capital Area.

### Core comparable universe (P0)

- Seoul: 25 basic local councils
- Gyeonggi: 31 basic local councils
- Incheon: 10 basic local councils

Total: **66 basic local councils**.

### Supplemental high-level universe (P0.5)

- Seoul Metropolitan Council
- Gyeonggi Provincial Council
- Incheon Metropolitan Council

These are stored separately as `regional_council` because their geography and spending patterns are not directly comparable with basic councils.

### Executive branch (P1)

Mayors / county heads / deputy heads are valuable Executive Dining signals, but are introduced after the council pipeline is stable. They use a separate source family (`executive_leadership`) so the site can distinguish legislative and executive spending patterns.

## Canonical jurisdiction fields

Newly ingested rows should carry:

- `region`: `서울`, `경기`, `인천`
- `jurisdiction`: canonical display name, e.g. `경기 수원시`, `인천 중구`
- `jurisdiction_level`: `basic_council` or `regional_council`
- `institution`: official institution name, e.g. `수원특례시의회`
- `source_family`: initially `council_leadership`

Legacy Seoul seed records may still contain only `origin` such as `중랑구`; UI and normalization code should treat those as Seoul basic-council records until migrated.

## Collection policy

1. Official council / government source only for expense rows.
2. Search engines and third-party sites are source-discovery aids, never canonical expense evidence.
3. Source discovery does not equal ingestion.
4. New attachment formats receive an explicit parser before publication.
5. PDF/HWP/XLSX rows are normalized into one event schema before entity matching.
6. Restaurant matching requires stable evidence; same merchant name alone is insufficient when branch ambiguity exists.
7. Source lineage must remain attached to every published event.

## Rollout

### Phase A — source registry

Register all 66 basic councils and the 3 regional councils. Mark only manually verified official listing pages as verified.

### Phase B — high-yield adapters

Prioritize jurisdictions that publish clean monthly XLSX or predictable quarterly PDF data. Initial verified examples include Suwon, Goyang, Seongnam, Hwaseong, Bupyeong, Gyeonggi Provincial Council and Incheon Metropolitan Council.

### Phase C — backfill

Backfill from the current seed start date (2024-12) where the official archive permits it. Preserve publication cadence (monthly / quarterly) separately from event date.

### Phase D — scoring

Recalculate Destination VIP using exact origin geography so that cross-Seoul/Gyeonggi/Incheon movement is meaningful. Keep `regional_council` in a separate comparison cohort by default.

## Why the expansion matters

The current Seoul-only model can label a restaurant in Gyeonggi as a destination but cannot see whether the same restaurant is also repeatedly selected by nearby Gyeonggi councils. Capital-region coverage enables a stronger signal: **cross-jurisdiction consensus** — the same restaurant independently selected by senior officials from multiple institutions.
