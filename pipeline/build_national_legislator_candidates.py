#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/national_legislator_2024_expense.json'
REPORTS = ROOT / 'reports'

# A row must have an explicit dining/refreshment purpose. Generic words such as
# '정책', '의원', '회의', or '의정활동' are intentionally NOT sufficient: they
# previously admitted car rental, party dues, printing and other non-dining spend.
MEAL_WORDS = (
    '식사', '식대', '간담', '오찬', '만찬', '조찬', '회식', '음식', '다과',
    '급식', '도시락', '케이터링', '식음',
)

ROW_EXCLUDE_WORDS = (
    '주유', '교통', '택시', '인쇄', '문자', '우편', '광고', '임차', '렌탈',
    '렌터카', '사무', '통신', '숙박', '항공', '기차', 'ktx', '기념품', '화환',
    '꽃', '후원금', '인건비', '급여', '자동차', '보험료', '수수료', '통행료',
)

# Merchant-name vetoes. These are deliberately structural/category words rather
# than a list of politically selected entities. They remove merchants that are
# evidently not restaurants even when the purpose text happens to mention a meal.
MERCHANT_BLOCK_WORDS = (
    '캐피탈', '렌탈', '렌터카', '렌트카', '하이플러스', '보험', '생명', '손해보험',
    '카드', '은행', '증권', '투자증권', '저축은행', '항공', '철도', '코레일',
    '고속도로', '톨게이트', '주유소', '충전소', '택시', '인쇄', '문화사',
    '아트콤', '디자인', '광고', '미디어', '신문', '방송', '우체국', '택배',
    '통신', '문구', '사무용', '꽃집', '화원', '정육', '마트', '슈퍼', '편의점',
    '백화점', '면세점', '호텔', '리조트', '여행사', '법무', '세무', '회계',
    '노무', '후원회', '의원연맹', '연구소', '포럼', '위원회', '의원실',
    '정당', '당사', '선거사무소', '캠프',
)

POLITICAL_ORG_NAMES = (
    '더불어민주당', '국민의힘', '조국혁신당', '개혁신당', '진보당', '정의당',
    '기본소득당', '사회민주당', '민주평화당', '바른미래당', '국민의당',
    '우리공화당', '민생당', '무소속',
)

EXACT_BLOCK = {
    '상호없음', '사용처없음', '미상', '알수없음', '알 수 없음',
    '우아한형제들', '국회후생복지위원회', '한국아동인구환경의원연맹',
    '국회아프리카새시대포럼', '더좋은미래', '엘에스씨푸드', '엘에스씨푸드(국회의사당)',
}


def t(v):
    return ' '.join(str(v or '').split()).strip()


def canon(v):
    s = re.sub(r'^(?:주식회사|\(주\)|㈜)\s*', '', t(v), flags=re.I).strip(' ,')
    s = re.sub(r'\s+', ' ', s)
    return s


def compact(v):
    return re.sub(r'[\s()（）\[\]{}·ㆍ._,/\\-]+', '', t(v)).lower()


def merchant_block_reason(name: str) -> str:
    n = canon(name)
    c = compact(n)
    if not n:
        return 'blank'
    if n in EXACT_BLOCK or c in {compact(x) for x in EXACT_BLOCK}:
        return 'exact_non_dining'
    if any(compact(x) == c for x in POLITICAL_ORG_NAMES):
        return 'political_org'
    if any(compact(x) in c for x in MERCHANT_BLOCK_WORDS):
        return 'non_dining_category'
    # OCR/private-person artefacts such as '김', '이', '박' should not become a restaurant.
    if re.fullmatch(r'[가-힣]', n):
        return 'single_person_token'
    # Card/terminal-style merchant strings that are mostly digits are not useful entities.
    if sum(ch.isdigit() for ch in n) >= max(4, len(n) // 2):
        return 'numeric_or_terminal'
    return ''


def explicit_meal_intent(r: dict) -> bool:
    purpose = t(r.get('purpose')).lower()
    category = t(r.get('category')).lower()
    s = f'{purpose} {category}'
    return any(x in s for x in MEAL_WORDS)


def row_is_meal_candidate(r: dict) -> tuple[bool, str]:
    merchant = canon(r.get('merchant'))
    if not merchant:
        return False, 'blank_merchant'
    combined = f"{t(r.get('purpose'))} {t(r.get('category'))} {merchant}".lower()
    if any(x.lower() in combined for x in ROW_EXCLUDE_WORDS):
        return False, 'row_non_dining'
    if not explicit_meal_intent(r):
        return False, 'no_explicit_meal_intent'
    reason = merchant_block_reason(merchant)
    if reason:
        return False, reason
    return True, ''


def score(visits: int, members: int, months: int, spend: int) -> float:
    # Avoid the old score saturating nearly every popular merchant at 100.
    repeat = min(math.log1p(visits) / math.log1p(200), 1.0)
    breadth = min(math.log1p(members) / math.log1p(80), 1.0)
    persistence = min(months / 12, 1.0)
    spend_norm = min(math.log1p(max(spend, 0)) / math.log1p(50_000_000), 1.0)
    return round(100 * (.34 * repeat + .34 * breadth + .17 * persistence + .15 * spend_norm), 1)


def main():
    if not RAW.exists():
        print('national legislator raw missing')
        return

    d = json.loads(RAW.read_text(encoding='utf-8'))
    accepted = []
    rejected = Counter()
    for r in d.get('rows', []):
        ok, reason = row_is_meal_candidate(r)
        if ok:
            accepted.append(r)
        else:
            rejected[reason] += 1

    groups = defaultdict(list)
    for r in accepted:
        groups[canon(r.get('merchant'))].append(r)

    out = []
    for name, items in groups.items():
        if not name:
            continue
        members = sorted({t(r.get('member')) for r in items if t(r.get('member'))})
        months = sorted({t(r.get('used_date'))[:7] for r in items if re.match(r'20\d{2}-\d{2}', t(r.get('used_date')))})
        visits = len(items)
        spend = sum(int(r.get('amount') or 0) for r in items if isinstance(r.get('amount'), (int, float)))
        s = score(visits, len(members), len(months), spend)
        pc = Counter(t(r.get('purpose')) for r in items if t(r.get('purpose')))
        out.append({
            'merchant': name,
            'score': s,
            'visits': visits,
            'member_count': len(members),
            'members': members[:20],
            'months': len(months),
            'spend': spend,
            'date_min': min([t(r.get('used_date')) for r in items if t(r.get('used_date'))] or ['']),
            'date_max': max([t(r.get('used_date')) for r in items if t(r.get('used_date'))] or ['']),
            'purpose_stats': [{'text': k, 'count': v} for k, v in pc.most_common(6)],
            'recent': [
                {
                    'date': t(r.get('used_date')),
                    'member': t(r.get('member')),
                    'district': t(r.get('district')),
                    'amount': int(r.get('amount') or 0),
                    'purpose': t(r.get('purpose')),
                    'source': t(r.get('source_url')),
                }
                for r in sorted(items, key=lambda x: t(x.get('used_date')), reverse=True)[:8]
            ],
        })

    eligible = [
        x for x in out
        if x['visits'] >= 3 and x['member_count'] >= 2 and x['months'] >= 2 and x['score'] >= 35
    ]
    eligible.sort(key=lambda x: (x['score'], x['member_count'], x['visits'], x['spend']), reverse=True)

    REPORTS.mkdir(exist_ok=True)
    payload = {
        'source': 'national_legislator_2024',
        'cohort': 'national_legislator',
        'publication_status': 'historical_derived_source',
        'raw_row_count': len(d.get('rows', [])),
        'explicit_meal_rows': len(accepted),
        'rejected_rows': dict(rejected.most_common()),
        'eligible_count': len(eligible),
        'candidates': eligible[:200],
    }
    (REPORTS / 'national-legislator-candidates.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    md = [
        '# National legislator dining candidates — 2024',
        '',
        '> Historical 2024 political-fund spending; source is a media-normalized dataset derived from NEC accounting reports.',
        '> Only rows with explicit dining intent are considered; obvious non-restaurant merchants are vetoed before ranking.',
        '',
        f"- Raw spending rows: **{len(d.get('rows', [])):,}**",
        f'- Explicit meal rows after merchant veto: **{len(accepted):,}**',
        f'- Eligible restaurant candidates: **{len(eligible):,}**',
        '',
        '## Filtered row reasons',
        '',
    ]
    for reason, count in rejected.most_common():
        md.append(f'- {reason}: {count:,}')
    md += [
        '',
        '| # | Merchant | Score | Visits | Members | Months | Spend |',
        '|---:|---|---:|---:|---:|---:|---:|',
    ]
    for i, x in enumerate(eligible[:100], 1):
        md.append(
            f"| {i} | {x['merchant'].replace('|','/')} | {x['score']:.1f} | "
            f"{x['visits']} | {x['member_count']} | {x['months']} | {x['spend']:,} |"
        )
    (REPORTS / 'national-legislator-candidates.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(json.dumps({
        'raw_rows': len(d.get('rows', [])),
        'meal_rows': len(accepted),
        'eligible': len(eligible),
        'top10': [x['merchant'] for x in eligible[:10]],
        'rejected': dict(rejected.most_common(8)),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
