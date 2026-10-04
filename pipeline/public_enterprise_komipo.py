#!/usr/bin/env python3
from __future__ import annotations
import html, io, json, re, ssl, time, urllib.parse, urllib.request, zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

from ingest_central_executive_expense import rows_from

ROOT=Path(__file__).resolve().parents[1]
DISCOVERY=ROOT/'reports'/'public-enterprise-discovery.json'
REGISTRY=ROOT/'sources'/'public_enterprise_registry.json'
UA='ExecutiveDiningSeoul/2.1 (+https://github.com/mrunderdog/executive-dining-seoul)'
BASE='https://www.komipo.co.kr/kor/board/BRD_000065/'
TAB='KH041301'; MN='FN010712'
CTX=ssl._create_unverified_context()  # GitHub runner misses part of KOMIPO's certificate chain.

def request(url,data=None,referer=None):
    headers={'User-Agent':UA,'Accept':'*/*'}
    if data is not None:headers['Content-Type']='application/x-www-form-urlencoded'
    if referer:headers['Referer']=referer
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,data=data,headers=headers)
            with urllib.request.urlopen(req,timeout=25,context=CTX) as r:return r.read(),r.headers
        except Exception as e:
            last=e
            if attempt<2:time.sleep(1.5*(attempt+1))
    raise last

def text(s):return ' '.join(html.unescape(re.sub(r'<[^>]+>',' ',s or '')).split())
def local(tag):return tag.split('}',1)[-1] if '}' in tag else tag

def hwpx_tables(blob):
    out=[]
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names=sorted(n for n in zf.namelist() if n.lower().startswith('contents/section') and n.lower().endswith('.xml'))
        for name in names:
            root=ET.fromstring(zf.read(name));tno=0
            for tbl in root.iter():
                if local(tbl.tag)!='tbl':continue
                tno+=1;rows=[]
                for tr in tbl.iter():
                    if local(tr.tag)!='tr':continue
                    row=[]
                    for tc in tr:
                        if local(tc.tag)!='tc':continue
                        parts=[n.text for n in tc.iter() if local(n.tag)=='t' and n.text]
                        row.append(' '.join(' '.join(parts).split()))
                    if any(row):rows.append(row)
                if rows:out.append((f'{name}-table{tno}',rows))
    return out

def document_tables(blob,file_name):
    if zipfile.is_zipfile(io.BytesIO(blob)):
        tables=hwpx_tables(blob)
        if tables:return tables
    return list(rows_from(blob,file_name))

def find_header(rows):
    keys=('사용일자','집행내역','사용처','집행금액');best=(-1,None)
    for i,row in enumerate(rows[:20]):
        joined=''.join(str(x or '') for x in row).replace(' ','')
        score=sum(k in joined for k in keys)
        if score>best[0]:best=(score,i)
    return best[1] if best[0]>=3 else None

def parse_date(raw,year,month):
    nums=[int(x) for x in re.findall(r'\d+',str(raw or ''))]
    try:
        if len(nums)>=3:
            y=nums[0]+2000 if nums[0]<100 else nums[0];return date(y,nums[1],nums[2]).isoformat()
        if len(nums)==2:return date(year,nums[0],nums[1]).isoformat()
        if len(nums)==1:return date(year,month,nums[0]).isoformat()
    except ValueError:pass
    return ''

def amount(raw):
    s=re.sub(r'[^0-9.-]','',str(raw or ''))
    try:return int(round(float(s))) if s else None
    except:return None

def people(raw):
    m=re.search(r'\d+',str(raw or ''));return int(m.group()) if m else None

def extract_rows(blob,file_name,year,month,source_url,seq):
    result=[]
    for sheet,rows in document_tables(blob,file_name):
        hi=find_header(rows)
        if hi is None:continue
        hdr=[''.join(str(x or '').split()).lower() for x in rows[hi]]
        def idx(*keys):
            for i,h in enumerate(hdr):
                if any(k.replace(' ','').lower() in h for k in keys):return i
            return None
        dm=idx('사용일자','집행일자');pm=idx('집행내역','목적');mm=idx('사용처','장소');gm=idx('집행구분','결제수단');nm=idx('인원');am=idx('집행금액','금액')
        if None in (dm,pm,mm,am):continue
        for ri,row in enumerate(rows[hi+1:],start=hi+2):
            if max(dm,pm,mm,am)>=len(row):continue
            used=parse_date(row[dm],year,month);merchant=' '.join(str(row[mm] or '').split());purpose=' '.join(str(row[pm] or '').split());value=amount(row[am])
            if not used or not merchant or merchant in {'계','합계'} or value is None:continue
            result.append({
                'source_key':'komipo','institution':'한국중부발전','cohort':'public_enterprise_leadership','role':'사장','department':'',
                'used_date':used,'used_time':'','merchant':merchant,'address':'','purpose':purpose,
                'people':people(row[nm]) if nm is not None and nm<len(row) else None,'amount':value,'source_amount_scale':1,
                'payment_method':' '.join(str(row[gm] or '').split()) if gm is not None and gm<len(row) else '',
                'source_category':'사장 업무추진비','source_url':source_url,'source_sheet':sheet,'source_row':ri,'row_id':f'komipo:{seq}:{sheet}:{ri}'
            })
    return result

def list_page(page_index,years):
    url=BASE+f'boardMain.do?mnCd={MN}&schTabCd={TAB}&pageIndex={page_index}'
    raw,_=request(url);doc=raw.decode('utf-8',errors='replace');posts={}
    for m in re.finditer(r'<a\b([^>]*)>(.*?)</a>',doc,re.S|re.I):
        attrs=m.group(1);label=text(m.group(2));sm=re.search(r'board\.view\([\'\"]?(\d+)',attrs,re.I)
        if not sm or '업무추진비' not in label or '사장' not in label:continue
        ym=re.search(r'(20\d{2})\D{0,8}(1[0-2]|0?[1-9])\s*월',label)
        if not ym:continue
        y,mo=int(ym.group(1)),int(ym.group(2))
        if y in years:posts[sm.group(1)]=(label,y,mo,page_index)
    return url,posts

def process_post(seq,item):
    title,y,mo,page_index=item
    referer=BASE+f'boardMain.do?mnCd={MN}&schTabCd={TAB}&pageIndex={page_index}'
    pdata=urllib.parse.urlencode({'pageIndex':str(page_index),'mnCd':MN,'boardSeq':seq,'schTabCd':TAB}).encode()
    raw,_=request(BASE+f'boardView.do?mnCd={MN}',pdata,referer);doc=raw.decode('utf-8',errors='replace')
    am=re.search(r"board\.download\('([^']+)'\s*,\s*'([^']+)'\).*?>([^<]+)</a>",doc,re.I|re.S)
    if not am:raise ValueError('attachment missing')
    atch,file_sn,file_name=am.group(1),am.group(2),text(am.group(3))
    fields={'pageIndex':str(page_index),'mnCd':MN,'boardSeq':seq,'boardCd':'BRD_000065','atchFileId':atch,'fileSn':file_sn,'formNo':'','schTabCd':TAB}
    blob,_=request('https://www.komipo.co.kr/atch/fileDown.do',urllib.parse.urlencode(fields).encode(),BASE+f'boardView.do?mnCd={MN}')
    detail_url=BASE+f'boardView.do?mnCd={MN}#boardSeq={seq}'
    return extract_rows(blob,file_name,y,mo,detail_url,seq)

def main():
    report=json.loads(DISCOVERY.read_text(encoding='utf-8'));reg=json.loads(REGISTRY.read_text(encoding='utf-8'))
    if not any(x.get('key')=='komipo' and x.get('publish') for x in reg.get('sources',[])):return
    target_year=int(report.get('year') or datetime.now().year);years={target_year,target_year-1};pages=[];posts={};errors=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs={pool.submit(list_page,p,years):p for p in range(1,5)}
        for fut in as_completed(futs):
            p=futs[fut]
            try:url,found=fut.result();pages.append(url);posts.update(found)
            except Exception as e:errors.append(f'listing {p}: {type(e).__name__}: {e}')
    inline=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs={pool.submit(process_post,seq,item):seq for seq,item in posts.items()}
        for fut in as_completed(futs):
            seq=futs[fut]
            try:inline.extend(fut.result())
            except Exception as e:errors.append(f'post {seq}: {type(e).__name__}: {e}')
    inline.sort(key=lambda r:(r.get('used_date',''),r.get('merchant','')))
    entry={'key':'komipo','institution':'한국중부발전','cohort':'public_enterprise_leadership','default_role':'사장','years':sorted(years),'pages':sorted(pages),'attachments':[],'inline_rows':inline,'errors':errors,'inline_replace':True,'parseable_attachments':len(posts),'status':'PARSEABLE_FOUND' if inline else ('FETCH_FAILED' if errors else 'NO_FILES_FOUND')}
    sources=report.get('sources') or [];replaced=False;out=[]
    for x in sources:
        if x.get('key')=='komipo':out.append(entry);replaced=True
        else:out.append(x)
    if not replaced:out.append(entry)
    report['sources']=out;DISCOVERY.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'posts':len(posts),'rows':len(inline),'merchants':len({x['merchant'] for x in inline}),'errors':errors[:8]},ensure_ascii=False))

if __name__=='__main__':main()
