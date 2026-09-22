#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data'/'raw'


def excel_serial_to_date(s):
    try:
        n=float(str(s).strip())
    except Exception:
        return None
    if not 20000 <= n <= 60000:
        return None
    return (datetime(1899,12,30)+timedelta(days=n)).date()


def parse_date_text(s):
    raw=str(s or '').strip()
    if not raw:
        return None
    # Time is frequently stored in the same disclosure cell as the date.
    raw=re.sub(r"\s+\d{1,2}:\d{2}(?::\d{2})?\s*$","",raw).strip()
    # Common council shorthand: 25.11.05. -> 2025-11-05.
    m=re.fullmatch(r"(\d{2})[./-](\d{1,2})[./-](\d{1,2})[.]?",raw)
    if m:
        try:
            return date(2000+int(m.group(1)),int(m.group(2)),int(m.group(3)))
        except ValueError:
            pass
    patterns=(
        r'^(20\d{2})-(\d{2})-(\d{2})$',
        r'^(20\d{2})(\d{2})(\d{2})$',
        r'^(20\d{2})-(\d{2})(\d{2})$',
        r'^(20\d{2})(\d{2})-(\d{2})$',
        r'^(20\d{2})[./](\d{1,2})[./](\d{1,2})[.]?$',
    )
    for pat in patterns:
        m=re.fullmatch(pat,raw)
        if not m:
            continue
        try:
            return date(*map(int,m.groups()))
        except ValueError:
            continue
    return None


def expected_period(period):
    if not period or len(period)<3:
        return None
    y,m,q=period
    if m:
        start=date(y,m,1)
        end=date(y,12,31) if m==12 else date(y,m+1,1)-timedelta(days=1)
        return start,end
    if q:
        sm=(q-1)*3+1
        em=q*3
        start=date(y,sm,1)
        end=date(y,12,31) if em==12 else date(y,em+1,1)-timedelta(days=1)
        return start,end
    return None


def self_test():
    samples={
        '2026-01-05':'2026-01-05',
        '20260105':'2026-01-05',
        '2026-0105':'2026-01-05',
        '202601-05':'2026-01-05',
        '2026.1.5':'2026-01-05',
        '2026/01/05':'2026-01-05',
        '25.11.05.':'2025-11-05',
        '25.11.18. 14:37':'2025-11-18',
        '25.11.24 19:54':'2025-11-24',
    }
    for raw,expected in samples.items():
        got=parse_date_text(raw)
        assert got and got.isoformat()==expected, (raw, got, expected)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',required=True)
    ap.add_argument('--min-valid',type=float,default=.95)
    ap.add_argument('--self-test',action='store_true')
    args=ap.parse_args()
    self_test()
    if args.self_test:
        print('repair_raw_dates self-test OK')
        return

    path=RAW/f'{args.source}_expense.json'
    d=json.loads(path.read_text(encoding='utf-8'))
    rows=d.get('rows',[])
    repaired_serial=0
    normalized_text_dates=0
    valid=0
    in_period=0
    transaction_rows=0
    transaction_valid=0
    transaction_in_period=0
    invalid_examples=[]

    for r in rows:
        raw=r.get('used_date','')
        period=expected_period(r.get('source_period'))
        dt=parse_date_text(raw)
        if dt and str(raw).strip()!=dt.isoformat():
            r['used_date']=dt.isoformat()
            normalized_text_dates+=1
        # Some public disclosure sheets omit the year and write dates as
        # "1월 12일". When source_period fixes the year, month/day is unambiguous
        # even for quarterly sheets, so normalize it before the quality gate.
        source_period=r.get('source_period')
        if not dt and source_period and source_period[0]:
            md=re.fullmatch(r"\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*",str(raw).strip())
            if md:
                try:
                    dt=date(int(source_period[0]),int(md.group(1)),int(md.group(2)))
                    r['used_date']=dt.isoformat()
                    normalized_text_dates+=1
                except ValueError:
                    pass
        # Monthly disclosure sheets can also abbreviate the date to the day
        # number only. This is safe only when source_period fixes year+month.
        if not dt and period and source_period and source_period[1] and re.fullmatch(r"\d{1,2}",str(raw).strip()):
            try:
                dt=date(int(source_period[0]),int(source_period[1]),int(str(raw).strip()))
                r['used_date']=dt.isoformat()
                normalized_text_dates+=1
            except ValueError:
                pass
        if not dt:
            dt=excel_serial_to_date(raw)
            if dt:
                r['used_date']=dt.isoformat()
                repaired_serial+=1

        ok=dt is not None
        ip=bool(dt and period and period[0] <= dt <= period[1])
        r['date_quality']='in_period' if ip else ('valid_outside_period' if ok else 'invalid')
        valid += int(ok)
        in_period += int(ip)
        is_transaction=bool(str(r.get('merchant') or '').strip())
        if is_transaction:
            transaction_rows += 1
            transaction_valid += int(ok)
            transaction_in_period += int(ip)
        if (not ok or (period and not ip)) and len(invalid_examples)<20:
            invalid_examples.append({
                'used_date':r.get('used_date'),
                'period':r.get('source_period'),
                'sheet':r.get('source_sheet'),
                'row':r.get('source_row'),
                'merchant':r.get('merchant'),
            })

    all_coverage=valid/len(rows) if rows else 0
    all_in_period_coverage=in_period/len(rows) if rows else 0
    coverage=transaction_valid/transaction_rows if transaction_rows else all_coverage
    in_period_coverage=transaction_in_period/transaction_rows if transaction_rows else all_in_period_coverage
    d['raw_quality']={
        'rows':len(rows),
        'transaction_rows':transaction_rows,
        'repaired_excel_serial_dates':repaired_serial,
        'normalized_text_dates':normalized_text_dates,
        'valid_date_coverage':round(coverage,4),
        'in_period_date_coverage':round(in_period_coverage,4),
        'all_row_valid_date_coverage':round(all_coverage,4),
        'all_row_in_period_date_coverage':round(all_in_period_coverage,4),
        'invalid_examples':invalid_examples,
    }
    path.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(d['raw_quality'],ensure_ascii=False,indent=2))
    if coverage < args.min_valid:
        raise SystemExit(f'valid date coverage {coverage:.1%} < {args.min_valid:.0%}')


if __name__=='__main__':
    main()
