#!/usr/bin/env python3
from __future__ import annotations
import json, math, re
from collections import Counter, defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'data/raw/national_legislator_2024_expense.json';REPORTS=ROOT/'reports'
MEAL_WORDS=('식사','간담','오찬','만찬','회의','협의','의정활동','정책','간담회','참석자','의원','보좌진')
EXCLUDE=('주유','교통','택시','인쇄','문자','우편','광고','임차','사무','통신','숙박','항공','기차','KTX','기념품','화환','꽃','후원금','인건비','급여')
def t(v):return ' '.join(str(v or '').split()).strip()
def canon(v):return re.sub(r'^(?:주식회사|\(주\)|㈜)\s*','',t(v)).strip(' ,')
def meal(r):
 s=(t(r.get('purpose'))+' '+t(r.get('category'))+' '+t(r.get('merchant')))
 return bool(t(r.get('merchant'))) and not any(x in s for x in EXCLUDE) and any(x in s for x in MEAL_WORDS)
def score(visits,members,months,spend):
 return round(100*(.35*min(math.log1p(visits)/math.log1p(12),1)+.35*min(members/6,1)+.15*min(months/8,1)+.15*min(math.log1p(max(spend,0))/math.log1p(4_000_000),1)),1)
def main():
 if not RAW.exists():print('national legislator raw missing');return
 d=json.loads(RAW.read_text(encoding='utf-8'));rows=[r for r in d.get('rows',[]) if meal(r)];g=defaultdict(list)
 for r in rows:g[canon(r.get('merchant'))].append(r)
 out=[]
 for name,items in g.items():
  if not name:continue
  members=sorted({t(r.get('member')) for r in items if t(r.get('member'))});months=sorted({t(r.get('used_date'))[:7] for r in items if re.match(r'20\d{2}-\d{2}',t(r.get('used_date')))})
  visits=len(items);spend=sum(int(r.get('amount') or 0) for r in items if isinstance(r.get('amount'),(int,float)));s=score(visits,len(members),len(months),spend);pc=Counter(t(r.get('purpose')) for r in items if t(r.get('purpose')))
  out.append({'merchant':name,'score':s,'visits':visits,'member_count':len(members),'members':members[:20],'months':len(months),'spend':spend,'date_min':min([t(r.get('used_date')) for r in items if t(r.get('used_date'))] or ['']),'date_max':max([t(r.get('used_date')) for r in items if t(r.get('used_date'))] or ['']),'purpose_stats':[{'text':k,'count':v} for k,v in pc.most_common(6)],'recent':[{'date':t(r.get('used_date')),'member':t(r.get('member')),'district':t(r.get('district')),'amount':int(r.get('amount') or 0),'purpose':t(r.get('purpose')),'source':t(r.get('source_url'))} for r in sorted(items,key=lambda x:t(x.get('used_date')),reverse=True)[:8]]})
 eligible=[x for x in out if x['visits']>=3 and x['member_count']>=2 and x['score']>=45];eligible.sort(key=lambda x:(x['score'],x['member_count'],x['visits'],x['spend']),reverse=True)
 REPORTS.mkdir(exist_ok=True);(REPORTS/'national-legislator-candidates.json').write_text(json.dumps({'source':'national_legislator_2024','cohort':'national_legislator','publication_status':'historical_derived_source','eligible_count':len(eligible),'candidates':eligible[:200]},ensure_ascii=False,indent=2),encoding='utf-8')
 md=['# National legislator dining candidates — 2024','', '> Historical 2024 political-fund spending; source is a media-normalized dataset derived from NEC accounting reports.','',f'- Meal-like rows: **{len(rows)}**',f'- Eligible merchants: **{len(eligible)}**','','| # | Merchant | Score | Visits | Members | Months | Spend |','|---:|---|---:|---:|---:|---:|---:|']
 for i,x in enumerate(eligible[:100],1):md.append(f"| {i} | {x['merchant'].replace('|','/')} | {x['score']:.1f} | {x['visits']} | {x['member_count']} | {x['months']} | {x['spend']:,} |")
 (REPORTS/'national-legislator-candidates.md').write_text('\n'.join(md)+'\n',encoding='utf-8');print(json.dumps({'meal_rows':len(rows),'eligible':len(eligible)},ensure_ascii=False))
if __name__=='__main__':main()
