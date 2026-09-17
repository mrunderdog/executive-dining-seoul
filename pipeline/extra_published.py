from __future__ import annotations
import json
from pathlib import Path
from published_sources import _category
ROOT=Path(__file__).resolve().parents[1];REPORTS=ROOT/'reports'
def t(v):return ' '.join(str(v or '').split()).strip()
def central_records(max_records=120):
 p=REPORTS/'central-executive-candidates.json'
 if not p.exists():return []
 d=json.loads(p.read_text(encoding='utf-8'));out=[]
 for rank,c in enumerate((d.get('candidates') or [])[:max_records],1):
  name=t(c.get('merchant'));address=t(c.get('address'))
  if not name:continue
  inst=c.get('institutions') or [];visits=int(c.get('visits') or 0);months=int(c.get('months') or 0);score=float(c.get('score') or 0);spend=int(c.get('spend') or 0)
  roles=[{'role':t(x.get('role')),'visits':int(x.get('visits') or 0),'people':0,'spend':0} for x in (c.get('role_stats') or []) if t(x.get('role'))]
  recent=[{'date':t(x.get('date')),'time':t(x.get('time')),'role':f"{t(x.get('institution'))} {t(x.get('role'))}".strip(),'people':int(x.get('people') or 0),'amount':int(x.get('amount') or 0),'purpose':t(x.get('purpose')),'source':t(x.get('source'))} for x in (c.get('recent') or [])]
  out.append({'name':name,'origin':'중앙정부','region':'전국','jurisdiction':'대한민국','institution':' · '.join(inst[:4]) or '중앙행정기관','type':'executive','destination':None,'executive':{'rank':rank,'score':round(score,1),'exec_events':visits,'roles':int(c.get('role_count') or 0),'months':months,'evening_ratio':0,'source':'central_executive'},'address':address,'search_query':f"{name} {address or '대한민국'}",'business':{'display':name,'category':_category(name),'phone':'','status':'중앙부처 공식 업무추진비 원자료상 사용처','rating':'','note':'중앙행정기관이 공개한 장·차관/고위직 업무추진비의 파싱 가능한 XLS/XLSX/CSV 원자료 기반.','url':''},'evidence':{'visits':visits,'spend':spend,'people':0,'months':months,'evening':0,'evening_ratio':0,'ppc':0,'date_min':t(c.get('date_min')),'date_max':t(c.get('date_max')),'roles':roles,'purposes':c.get('purpose_stats') or [],'recent':recent,'source_rows':[]},'why':f"중앙행정기관 공식 업무추진비에서 {visits}회, {len(inst)}개 기관/공개 직위군에 걸쳐 확인된 사용처입니다.",'published_source':'central_executive','cohort':'central_executive'})
 return out
def legislator_records(max_records=80):
 p=REPORTS/'national-legislator-candidates.json'
 if not p.exists():return []
 d=json.loads(p.read_text(encoding='utf-8'));out=[]
 for rank,c in enumerate((d.get('candidates') or [])[:max_records],1):
  name=t(c.get('merchant'))
  if not name:continue
  visits=int(c.get('visits') or 0);members=int(c.get('member_count') or 0);months=int(c.get('months') or 0);score=float(c.get('score') or 0);spend=int(c.get('spend') or 0)
  recent=[{'date':t(x.get('date')),'time':'','role':f"국회의원 {t(x.get('member'))}",'people':0,'amount':int(x.get('amount') or 0),'purpose':t(x.get('purpose')),'source':t(x.get('source'))} for x in (c.get('recent') or [])]
  roles=[{'role':f"국회의원 {m}",'visits':0,'people':0,'spend':0} for m in (c.get('members') or [])[:12]]
  out.append({'name':name,'origin':'국회(정치자금 2024)','region':'전국','jurisdiction':'대한민국','institution':'국회의원','type':'executive','destination':None,'executive':{'rank':rank,'score':round(score,1),'exec_events':visits,'roles':members,'months':months,'evening_ratio':0,'source':'national_legislator_2024'},'address':'','search_query':f"{name} 대한민국",'business':{'display':name,'category':_category(name),'phone':'','status':'2024년 국회의원 정치자금 지출내역 사용처','rating':'','note':'중앙선관위 회계보고서를 정보공개로 확보해 오마이뉴스·경향신문·뉴스타파가 OCR/정제한 2024 데이터의 식사성 지출 후보. 최신 2026 현황이 아니라 historical signal입니다.','url':'https://github.com/OhmyNews/KA-money'},'evidence':{'visits':visits,'spend':spend,'people':0,'months':months,'evening':0,'evening_ratio':0,'ppc':0,'date_min':t(c.get('date_min')),'date_max':t(c.get('date_max')),'roles':roles,'purposes':c.get('purpose_stats') or [],'recent':recent,'source_rows':[]},'why':f"2024년 국회의원 정치자금 지출자료에서 {visits}회, {members}명의 의원에게서 반복 확인된 사용처입니다. 정치적 평가가 아닌 식당 선택 패턴 신호입니다.",'published_source':'national_legislator_2024','cohort':'national_legislator','historical':True})
 return out
def merge_extra_published(payload:dict)->dict:
 payload=dict(payload);base=list(payload.get('records',[]));seen={(t(r.get('name')),t(r.get('origin'))) for r in base};added=[]
 for r in central_records()+legislator_records():
  k=(t(r.get('name')),t(r.get('origin')))
  if k in seen:continue
  seen.add(k);added.append(r)
 records=base+added;payload['records']=records;payload['origins']=sorted({t(r.get('origin')) for r in records if t(r.get('origin'))})
 stats=dict(payload.get('stats') or {});stats['total']=len(records);stats['supplemental']=int(stats.get('supplemental') or 0)+len(added);stats['executive']=sum(bool(r.get('executive')) for r in records);stats['destination']=sum(bool(r.get('destination')) for r in records);stats['both']=sum(bool(r.get('destination')) and bool(r.get('executive')) for r in records);payload['stats']=stats
 meta=dict(payload.get('meta') or {});ps=dict(meta.get('published_supplements') or {});ps['central_executive']=sum(r.get('published_source')=='central_executive' for r in added);ps['national_legislator_2024']=sum(r.get('published_source')=='national_legislator_2024' for r in added);meta['published_supplements']=ps;meta['scope']='수도권·중앙정부·국회 공공부문 Executive Dining';payload['meta']=meta
 return payload
