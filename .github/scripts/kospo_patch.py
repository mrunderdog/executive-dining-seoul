import json
from pathlib import Path

p=Path('pipeline/public_enterprise_discovery.py')
s=p.read_text(encoding='utf-8')
anchor='def discover_kdhc(src,year):\n'
fn='''def discover_kospo(src,year):
    base=(src.get("listing_urls") or [""])[0]
    lookback=max(0,int(src.get("lookback_years",2)))
    years=sorted({year-i for i in range(lookback+1)})
    out={"key":src["key"],"institution":src["institution"],"cohort":src.get("cohort","public_enterprise_leadership"),"default_role":src.get("default_role","사장"),"years":years,"pages":[base],"attachments":[],"errors":[]}
    try:doc=fetch(base)
    except Exception as e:
        out["errors"].append(f"listing {base}: {type(e).__name__}: {e}")
        out["parseable_attachments"]=0;out["status"]="FETCH_FAILED";return out
    dm=re.search(r'disclosureNo\\s*:\\s*"([^\"]+)"',doc) or re.search(r'\\$submissionNo\\s*=\\s*"?([0-9]+)',doc)
    if not dm:
        out["errors"].append("ALIO disclosureNo missing")
        out["parseable_attachments"]=0;out["status"]="NO_FILES_FOUND";return out
    disclosure=dm.group(1)
    seen=set()
    for fm in re.finditer(r'<option\\s+value="([^\"]+)">\\s*([^<]+\\.(?:xlsx?|xls))\\s*</option>',doc,re.I):
        file_no,label=fm.group(1),html.unescape(fm.group(2)).strip()
        ym=re.search(r'(20\\d{2})',label)
        if not ym:continue
        y=int(ym.group(1))
        if y not in years:continue
        url=f"https://www.alio.go.kr/download/file.json?d={disclosure}&f={file_no}"
        if url in seen:continue
        seen.add(url)
        out["attachments"].append({"text":label,"url":url,"download_url":url,"year":y,"month":None,"parent":base,"attachment_id":f"{disclosure}|{file_no}"})
    out["parseable_attachments"]=len(out["attachments"])
    out["status"]="PARSEABLE_FOUND" if out["attachments"] else "NO_FILES_FOUND"
    return out

'''
if 'def discover_kospo(src,year):' not in s:
    if anchor not in s: raise SystemExit('discovery insertion anchor missing')
    s=s.replace(anchor,fn+anchor)
dispatch='    if src.get("key")=="kdhc" and src.get("verified") and src.get("publish"):\n        return discover_kdhc(src,year)\n'
repl=dispatch+'    if src.get("key")=="kospo" and src.get("verified") and src.get("publish"):\n        return discover_kospo(src,year)\n'
if 'return discover_kospo(src,year)' not in s:
    if dispatch not in s: raise SystemExit('dispatch anchor missing')
    s=s.replace(dispatch,repl)
p.write_text(s,encoding='utf-8')

q=Path('pipeline/ingest_central_executive_expense.py')
t=q.read_text(encoding='utf-8')
loop='    for ri,row in enumerate(rows[hi+1:],start=hi+2):\n'
if '    kospo_category=""\n' not in t:
    if loop not in t: raise SystemExit('row loop anchor missing')
    t=t.replace(loop,'    kospo_category=""\n'+loop,1)
anchor2='        if meta.get("key")=="kogas":\n            source_category=role\n            role=clean(meta.get("default_role")) or "기관장"\n'
robust=anchor2+'        if meta.get("key")=="kospo":\n            raw_category=clean(cell(row,m,"role"))\n            if raw_category:\n                kospo_category=raw_category\n            source_category=kospo_category\n            role=clean(meta.get("default_role")) or "사장"\n'
simple=anchor2+'        if meta.get("key")=="kospo":\n            source_category=role\n            role=clean(meta.get("default_role")) or "사장"\n'
if simple in t:
    t=t.replace(simple,robust)
elif 'raw_category=clean(cell(row,m,"role"))' not in t:
    if anchor2 not in t: raise SystemExit('normalizer anchor missing')
    t=t.replace(anchor2,robust)
date_anchor='        if meta.get("key")=="kogas" and not re.fullmatch(r"20\\d{2}-\\d{2}-\\d{2}", d or ""):\n            continue\n'
date_repl=date_anchor+'        if meta.get("key")=="kospo" and not re.fullmatch(r"20\\d{2}-\\d{2}-\\d{2}", d or ""):\n            continue\n'
if 'meta.get("key")=="kospo" and not re.fullmatch' not in t:
    if date_anchor not in t: raise SystemExit('date filter anchor missing')
    t=t.replace(date_anchor,date_repl)
q.write_text(t,encoding='utf-8')

r=Path('sources/public_enterprise_registry.json')
d=json.loads(r.read_text(encoding='utf-8'))
d['as_of']='2026-10-02'
d['sources']=[x for x in d['sources'] if x.get('key') not in {'kospo','kowepo','ewp'}]
d['sources'].extend([
  {'key':'kospo','institution':'한국남부발전','cohort':'public_enterprise_leadership','verified':True,'publish':True,'refresh_policy':'monthly','default_role':'사장','format_hint':'xlsx-alio-detail','lookback_years':2,'listing_urls':['https://www.alio.go.kr/mobile/item/itemReportTerm.do?apbaId=C0043&disclosureNo=&reportFormRootNo=20701'],'note':'ALIO 기관장 업무추진비 정기공시(C0043 / 20701). 공식 XLSX에 일자·목적·장소·참석대상·참석인원·금액의 거래별 세부내역이 공개되어 최근 2개 완료연도 중심으로 연도별 ALIO XLSX adapter로 수집.'},
  {'key':'kowepo','institution':'한국서부발전','cohort':'public_enterprise_leadership','verified':True,'publish':False,'refresh_policy':'track_only','default_role':'기관장','format_hint':'xlsx-aggregate-only','listing_urls':['https://www.alio.go.kr/mobile/item/itemReportTerm.do?apbaId=C0082&disclosureNo=&reportFormRootNo=20701'],'note':'ALIO 2025 공식 XLSX를 직접 검증했으나 집행월·집행내역·건수·집행금액만 있고 merchant/사용처가 없어 지도 데이터로 출판 불가.'},
  {'key':'ewp','institution':'한국동서발전','cohort':'public_enterprise_leadership','verified':True,'publish':False,'refresh_policy':'track_only','default_role':'기관장','format_hint':'xlsx-aggregate-only','listing_urls':['https://www.alio.go.kr/mobile/item/itemReportTerm.do?apbaId=C0066&disclosureNo=&reportFormRootNo=20701'],'note':'ALIO 2025 공식 XLSX를 직접 검증했으나 집행월·집행내역·금액만 있고 merchant/사용처가 없어 지도 데이터로 출판 불가.'}
])
r.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
