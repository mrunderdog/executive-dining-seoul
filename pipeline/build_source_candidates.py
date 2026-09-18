#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data'/'raw'
REPORTS=ROOT/'reports'

MEAL_WORDS=('간담','식사','오찬','만찬','업무','협의','논의','의정','관계자','현안','의견','격려','소통')
EXCLUDE_WORDS=('마트','편의점','문구','주유','주차','택시','철도','고속도로','온라인','네이버','쿠팡','다이소','꽃','화원','기념품','구입','물품','카페','커피','스타벅스','이디야','베이커리','빵','사무실')
AMBIGUOUS_MERCHANTS=('(주)신화푸드','신화푸드')


def looks_meal(r):
    purpose=str(r.get('purpose') or '')
    merchant=str(r.get('merchant') or '')
    if merchant in AMBIGUOUS_MERCHANTS: return False
    if any(x in purpose+merchant for x in EXCLUDE_WORDS): return False
    return any(x in purpose for x in MEAL_WORDS) or bool(merchant)


def role_bucket(role):
    s=re.sub(r'\s+','',str(role or ''))
    # Some councils suffix the sheet role with a month, e.g. 의장(8월),
    # 부의장(10월). Keep the leadership scope conservative while accepting
    # those presentation variants.
    if re.match(r'^의장(?:\(|$)', s): return '의장'
    if re.match(r'^부의장(?:\(|$)', s): return '부의장'
    return None


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',required=True); ap.add_argument('--top',type=int,default=50); args=ap.parse_args()
    d=json.loads((RAW/f'{args.source}_expense.json').read_text(encoding='utf-8'))
    rows=[r for r in d.get('rows',[]) if r.get('date_quality')=='in_period' and looks_meal(r)]
    groups=defaultdict(list)
    for r in rows:
        rb=role_bucket(r.get('role'))
        if not rb: continue
        name=' '.join(str(r.get('merchant') or '').split())
        if not name: continue
        groups[name].append((rb,r))
    out=[]
    for name,items in groups.items():
        visits=len(items)
        roles=sorted(set(rb for rb,_ in items))
        spend=sum(int(r.get('amount') or 0) for _,r in items)
        months=sorted(set((r.get('used_date') or '')[:7] for _,r in items if re.match(r'20\d{2}-\d{2}',r.get('used_date') or '')))
        people=sum(int(r.get('people') or 0) for _,r in items)
        evenings=0
        for _,r in items:
            m=re.match(r'(\d{1,2})[:시]',str(r.get('used_time') or ''))
            if m and int(m.group(1))>=17: evenings+=1
        score=min(100, round(35*min(visits/10,1)+25*min(len(months)/5,1)+20*min(len(roles)/2,1)+10*(evenings/visits if visits else 0)+10*min(spend/3_000_000,1),1))
        out.append({'merchant':name,'visits':visits,'roles':roles,'months':len(months),'spend':spend,'people':people,'evening_ratio':round(evenings/visits,3) if visits else 0,'score':score})
    out.sort(key=lambda x:(x['score'],x['visits'],x['spend']),reverse=True)
    REPORTS.mkdir(exist_ok=True)
    md=REPORTS/f'{args.source}-executive-candidates.md'
    lines=[f'# {args.source} Executive-repeat candidates','',f'Rows considered: {len(rows)}','', '> Exploratory candidate ranking only. It is not a food-quality score and is not yet published to the map.','', '| # | Merchant | Score | Chair/Vice visits | Roles | Months | Spend | Evening |','|---:|---|---:|---:|---|---:|---:|---:|']
    for i,x in enumerate(out[:args.top],1):
        lines.append(f"| {i} | {x['merchant'].replace('|','/')} | {x['score']:.1f} | {x['visits']} | {', '.join(x['roles'])} | {x['months']} | {x['spend']:,} | {x['evening_ratio']:.0%} |")
    md.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    js=REPORTS/f'{args.source}-executive-candidates.json'
    js.write_text(json.dumps({'source':args.source,'candidate_count':len(out),'candidates':out},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'source':args.source,'candidates':len(out),'top':out[:5]},ensure_ascii=False))

if __name__=='__main__': main()
