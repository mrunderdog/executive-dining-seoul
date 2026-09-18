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
    # Excel 1900 date system, accounting for the historical leap-year bug.
    return (datetime(1899,12,30)+timedelta(days=n)).date()


def parse_iso(s):
    raw=str(s or '').strip()
    if not raw:
        return None
    patterns = (
        r'^(20\d{2})-(\d{2})-(\d{2})


def expected_period(period):
    if not period or len(period)<3: return None
    y,m,q=period
    if m:
        start=date(y,m,1)
        if m==12: end=date(y,12,31)
        else: end=date(y,m+1,1)-timedelta(days=1)
        return start,end
    if q:
        sm=(q-1)*3+1
        em=q*3
        start=date(y,sm,1)
        if em==12: end=date(y,12,31)
        else: end=date(y,em+1,1)-timedelta(days=1)
        return start,end
    return None


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',required=True); ap.add_argument('--min-valid',type=float,default=.95); args=ap.parse_args()
    path=RAW/f'{args.source}_expense.json'
    d=json.loads(path.read_text(encoding='utf-8'))
    rows=d.get('rows',[])
    repaired=normalized_text_dates=valid=in_period=0
    invalid_examples=[]
    for r in rows:
        s=r.get('used_date','')
        dt=parse_iso(s)
        if dt and str(s).strip() != dt.isoformat():
            r['used_date']=dt.isoformat(); normalized_text_dates+=1
        if not dt:
            x=excel_serial_to_date(s)
            if x:
                r['used_date']=x.isoformat(); dt=x; repaired+=1
        period=expected_period(r.get('source_period'))
        ok=dt is not None
        ip=bool(dt and period and period[0] <= dt <= period[1])
        r['date_quality']='in_period' if ip else ('valid_outside_period' if ok else 'invalid')
        valid += int(ok)
        in_period += int(ip)
        if (not ok or (period and not ip)) and len(invalid_examples)<20:
            invalid_examples.append({'used_date':r.get('used_date'),'period':r.get('source_period'),'sheet':r.get('source_sheet'),'row':r.get('source_row'),'merchant':r.get('merchant')})
    coverage=valid/len(rows) if rows else 0
    in_period_coverage=in_period/len(rows) if rows else 0
    d['raw_quality']={'rows':len(rows),'repaired_excel_serial_dates':repaired,'normalized_text_dates':normalized_text_dates,'valid_date_coverage':round(coverage,4),'in_period_date_coverage':round(in_period_coverage,4),'invalid_examples':invalid_examples}
    path.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(d['raw_quality'],ensure_ascii=False,indent=2))
    if coverage < args.min_valid:
        raise SystemExit(f'valid date coverage {coverage:.1%} < {args.min_valid:.0%}')

if __name__=='__main__': main()
,
        r'^(20\d{2})(\d{2})(\d{2})


def expected_period(period):
    if not period or len(period)<3: return None
    y,m,q=period
    if m:
        start=date(y,m,1)
        if m==12: end=date(y,12,31)
        else: end=date(y,m+1,1)-timedelta(days=1)
        return start,end
    if q:
        sm=(q-1)*3+1
        em=q*3
        start=date(y,sm,1)
        if em==12: end=date(y,12,31)
        else: end=date(y,em+1,1)-timedelta(days=1)
        return start,end
    return None


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',required=True); ap.add_argument('--min-valid',type=float,default=.95); args=ap.parse_args()
    path=RAW/f'{args.source}_expense.json'
    d=json.loads(path.read_text(encoding='utf-8'))
    rows=d.get('rows',[])
    repaired=valid=in_period=0
    invalid_examples=[]
    for r in rows:
        s=r.get('used_date','')
        dt=parse_iso(s)
        if not dt:
            x=excel_serial_to_date(s)
            if x:
                r['used_date']=x.isoformat(); dt=x; repaired+=1
        period=expected_period(r.get('source_period'))
        ok=dt is not None
        ip=bool(dt and period and period[0] <= dt <= period[1])
        r['date_quality']='in_period' if ip else ('valid_outside_period' if ok else 'invalid')
        valid += int(ok)
        in_period += int(ip)
        if (not ok or (period and not ip)) and len(invalid_examples)<20:
            invalid_examples.append({'used_date':r.get('used_date'),'period':r.get('source_period'),'sheet':r.get('source_sheet'),'row':r.get('source_row'),'merchant':r.get('merchant')})
    coverage=valid/len(rows) if rows else 0
    in_period_coverage=in_period/len(rows) if rows else 0
    d['raw_quality']={'rows':len(rows),'repaired_excel_serial_dates':repaired,'valid_date_coverage':round(coverage,4),'in_period_date_coverage':round(in_period_coverage,4),'invalid_examples':invalid_examples}
    path.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(d['raw_quality'],ensure_ascii=False,indent=2))
    if coverage < args.min_valid:
        raise SystemExit(f'valid date coverage {coverage:.1%} < {args.min_valid:.0%}')

if __name__=='__main__': main()
,
        r'^(20\d{2})-(\d{2})(\d{2})


def expected_period(period):
    if not period or len(period)<3: return None
    y,m,q=period
    if m:
        start=date(y,m,1)
        if m==12: end=date(y,12,31)
        else: end=date(y,m+1,1)-timedelta(days=1)
        return start,end
    if q:
        sm=(q-1)*3+1
        em=q*3
        start=date(y,sm,1)
        if em==12: end=date(y,12,31)
        else: end=date(y,em+1,1)-timedelta(days=1)
        return start,end
    return None


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',required=True); ap.add_argument('--min-valid',type=float,default=.95); args=ap.parse_args()
    path=RAW/f'{args.source}_expense.json'
    d=json.loads(path.read_text(encoding='utf-8'))
    rows=d.get('rows',[])
    repaired=valid=in_period=0
    invalid_examples=[]
    for r in rows:
        s=r.get('used_date','')
        dt=parse_iso(s)
        if not dt:
            x=excel_serial_to_date(s)
            if x:
                r['used_date']=x.isoformat(); dt=x; repaired+=1
        period=expected_period(r.get('source_period'))
        ok=dt is not None
        ip=bool(dt and period and period[0] <= dt <= period[1])
        r['date_quality']='in_period' if ip else ('valid_outside_period' if ok else 'invalid')
        valid += int(ok)
        in_period += int(ip)
        if (not ok or (period and not ip)) and len(invalid_examples)<20:
            invalid_examples.append({'used_date':r.get('used_date'),'period':r.get('source_period'),'sheet':r.get('source_sheet'),'row':r.get('source_row'),'merchant':r.get('merchant')})
    coverage=valid/len(rows) if rows else 0
    in_period_coverage=in_period/len(rows) if rows else 0
    d['raw_quality']={'rows':len(rows),'repaired_excel_serial_dates':repaired,'valid_date_coverage':round(coverage,4),'in_period_date_coverage':round(in_period_coverage,4),'invalid_examples':invalid_examples}
    path.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(d['raw_quality'],ensure_ascii=False,indent=2))
    if coverage < args.min_valid:
        raise SystemExit(f'valid date coverage {coverage:.1%} < {args.min_valid:.0%}')

if __name__=='__main__': main()
,
        r'^(20\d{2})(\d{2})-(\d{2})


def expected_period(period):
    if not period or len(period)<3: return None
    y,m,q=period
    if m:
        start=date(y,m,1)
        if m==12: end=date(y,12,31)
        else: end=date(y,m+1,1)-timedelta(days=1)
        return start,end
    if q:
        sm=(q-1)*3+1
        em=q*3
        start=date(y,sm,1)
        if em==12: end=date(y,12,31)
        else: end=date(y,em+1,1)-timedelta(days=1)
        return start,end
    return None


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',required=True); ap.add_argument('--min-valid',type=float,default=.95); args=ap.parse_args()
    path=RAW/f'{args.source}_expense.json'
    d=json.loads(path.read_text(encoding='utf-8'))
    rows=d.get('rows',[])
    repaired=valid=in_period=0
    invalid_examples=[]
    for r in rows:
        s=r.get('used_date','')
        dt=parse_iso(s)
        if not dt:
            x=excel_serial_to_date(s)
            if x:
                r['used_date']=x.isoformat(); dt=x; repaired+=1
        period=expected_period(r.get('source_period'))
        ok=dt is not None
        ip=bool(dt and period and period[0] <= dt <= period[1])
        r['date_quality']='in_period' if ip else ('valid_outside_period' if ok else 'invalid')
        valid += int(ok)
        in_period += int(ip)
        if (not ok or (period and not ip)) and len(invalid_examples)<20:
            invalid_examples.append({'used_date':r.get('used_date'),'period':r.get('source_period'),'sheet':r.get('source_sheet'),'row':r.get('source_row'),'merchant':r.get('merchant')})
    coverage=valid/len(rows) if rows else 0
    in_period_coverage=in_period/len(rows) if rows else 0
    d['raw_quality']={'rows':len(rows),'repaired_excel_serial_dates':repaired,'valid_date_coverage':round(coverage,4),'in_period_date_coverage':round(in_period_coverage,4),'invalid_examples':invalid_examples}
    path.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(d['raw_quality'],ensure_ascii=False,indent=2))
    if coverage < args.min_valid:
        raise SystemExit(f'valid date coverage {coverage:.1%} < {args.min_valid:.0%}')

if __name__=='__main__': main()
,
        r'^(20\d{2})[./](\d{1,2})[./](\d{1,2})[.]?


def expected_period(period):
    if not period or len(period)<3: return None
    y,m,q=period
    if m:
        start=date(y,m,1)
        if m==12: end=date(y,12,31)
        else: end=date(y,m+1,1)-timedelta(days=1)
        return start,end
    if q:
        sm=(q-1)*3+1
        em=q*3
        start=date(y,sm,1)
        if em==12: end=date(y,12,31)
        else: end=date(y,em+1,1)-timedelta(days=1)
        return start,end
    return None


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',required=True); ap.add_argument('--min-valid',type=float,default=.95); args=ap.parse_args()
    path=RAW/f'{args.source}_expense.json'
    d=json.loads(path.read_text(encoding='utf-8'))
    rows=d.get('rows',[])
    repaired=valid=in_period=0
    invalid_examples=[]
    for r in rows:
        s=r.get('used_date','')
        dt=parse_iso(s)
        if not dt:
            x=excel_serial_to_date(s)
            if x:
                r['used_date']=x.isoformat(); dt=x; repaired+=1
        period=expected_period(r.get('source_period'))
        ok=dt is not None
        ip=bool(dt and period and period[0] <= dt <= period[1])
        r['date_quality']='in_period' if ip else ('valid_outside_period' if ok else 'invalid')
        valid += int(ok)
        in_period += int(ip)
        if (not ok or (period and not ip)) and len(invalid_examples)<20:
            invalid_examples.append({'used_date':r.get('used_date'),'period':r.get('source_period'),'sheet':r.get('source_sheet'),'row':r.get('source_row'),'merchant':r.get('merchant')})
    coverage=valid/len(rows) if rows else 0
    in_period_coverage=in_period/len(rows) if rows else 0
    d['raw_quality']={'rows':len(rows),'repaired_excel_serial_dates':repaired,'valid_date_coverage':round(coverage,4),'in_period_date_coverage':round(in_period_coverage,4),'invalid_examples':invalid_examples}
    path.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(d['raw_quality'],ensure_ascii=False,indent=2))
    if coverage < args.min_valid:
        raise SystemExit(f'valid date coverage {coverage:.1%} < {args.min_valid:.0%}')

if __name__=='__main__': main()
,
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
    if not period or len(period)<3: return None
    y,m,q=period
    if m:
        start=date(y,m,1)
        if m==12: end=date(y,12,31)
        else: end=date(y,m+1,1)-timedelta(days=1)
        return start,end
    if q:
        sm=(q-1)*3+1
        em=q*3
        start=date(y,sm,1)
        if em==12: end=date(y,12,31)
        else: end=date(y,em+1,1)-timedelta(days=1)
        return start,end
    return None


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',required=True); ap.add_argument('--min-valid',type=float,default=.95); args=ap.parse_args()
    path=RAW/f'{args.source}_expense.json'
    d=json.loads(path.read_text(encoding='utf-8'))
    rows=d.get('rows',[])
    repaired=valid=in_period=0
    invalid_examples=[]
    for r in rows:
        s=r.get('used_date','')
        dt=parse_iso(s)
        if not dt:
            x=excel_serial_to_date(s)
            if x:
                r['used_date']=x.isoformat(); dt=x; repaired+=1
        period=expected_period(r.get('source_period'))
        ok=dt is not None
        ip=bool(dt and period and period[0] <= dt <= period[1])
        r['date_quality']='in_period' if ip else ('valid_outside_period' if ok else 'invalid')
        valid += int(ok)
        in_period += int(ip)
        if (not ok or (period and not ip)) and len(invalid_examples)<20:
            invalid_examples.append({'used_date':r.get('used_date'),'period':r.get('source_period'),'sheet':r.get('source_sheet'),'row':r.get('source_row'),'merchant':r.get('merchant')})
    coverage=valid/len(rows) if rows else 0
    in_period_coverage=in_period/len(rows) if rows else 0
    d['raw_quality']={'rows':len(rows),'repaired_excel_serial_dates':repaired,'valid_date_coverage':round(coverage,4),'in_period_date_coverage':round(in_period_coverage,4),'invalid_examples':invalid_examples}
    path.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(d['raw_quality'],ensure_ascii=False,indent=2))
    if coverage < args.min_valid:
        raise SystemExit(f'valid date coverage {coverage:.1%} < {args.min_valid:.0%}')

if __name__=='__main__': main()
