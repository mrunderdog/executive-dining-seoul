#!/usr/bin/env python3
from __future__ import annotations
import html, json, re, ssl, urllib.parse, urllib.request, zipfile, io
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DISCOVERY=ROOT/'reports'/'public-enterprise-discovery.json'
REGISTRY=ROOT/'sources'/'public_enterprise_registry.json'
UA='ExecutiveDiningSeoul/2.1 (+https://github.com/mrunderdog/executive-dining-seoul)'
BASE='https://www.komipo.co.kr/kor/board/BRD_000065/'
TAB='KH041301'
MN='FN010712'
CTX=ssl._create_unverified_context()  # KOMIPO runner certificate chain is incomplete.

def request(url,data=None,referer=None):
    headers={'User-Agent':UA,'Accept':'*/*'}
    if data is not None:headers['Content-Type']='application/x-www-form-urlencoded'
    if referer:headers['Referer']=referer
    req=urllib.request.Request(url,data=data,headers=headers)
    with urllib.request.urlopen(req,timeout=40,context=CTX) as r:
        return r.read(),r.headers

def text(s):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>',' ',s or '')).split())

def local(tag): return tag.split('}',1)[-1] if '}' in tag else tag

def hwpx_tables(blob):
    out=[]
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for name in sorted(n for n in zf.namelist() if n.lower().startswith('contents/section') and n.lower().endswith('.xml')):
            root=ET.fromstring(zf.read(name)); tno=0
            for tbl in root.iter():
                if local(tbl.tag)!='tbl':continue
                tno+=1; rows=[]
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

def find_header(rows):
    required=('사용일자','집 행 내 역','집행내역','사용처','집행금액')
    best=None
    for i,row in enumerate(rows[:20]):
        joined=' '.join(row).replace(' ','')
        score=sum(x.replace(' ','') in joined for x in required)
        if best is None or score>best[0]:best=(score,i)
    return best[1] if best and best[0]>=3 else None

def parse_date(raw,year,month):
    s=' '.join(str(raw or '').split())
    nums=[int(x) for x in re.findall(r'\d+',s)]
    try:
        if len(nums)>=3:
            y=nums[0]+2000 if nums[0]<100 else nums[0]
            return date(y,nums[1],nums[2]).isoformat()
        if len(nums)==2:return date(year,nums[0],nums[1]).isoformat()
        if len(nums)==1:return date(year,month,nums[0]).isoformat()
    except ValueError:return ''
    return ''

def amount(raw):
    s=re.sub(r'[^0-9.-]','',str(raw or ''))
    try:return int(round(float(s))) if s else None
    except:return None

def people(raw):
    m=re.search(r'\d+',str(raw or ''));return int(m.group()) if m else None

def extract_rows(blob,year,month,source_url,seq):
    result=[]
    for sheet,rows in hwpx_tables(blob):
        hi=find_header(rows)
        if hi is None:continue
        hdr=[''.join(str(x or '').split()).replace('(명)','').replace('(원,vat별도)','') for x in rows[hi]]
        def idx(*keys):
            for i,h in enumerate(hdr):
                if any(k.replace(' ','') in h for k in keys):return i
            return None
        dm=idx('사용일자','집행일자'); pm=idx('집행내역','목적'); mm=idx('사용처','장소'); gm=idx('집행구분','결제수단'); nm=idx('인원'); am=idx('집행금액','금액')
        if None in (dm,pm,mm,am):continue
        for ri,row in enumerate(rows[hi+1:],start=hi+2):
            if max(dm,pm,mm,am)>=len(row):continue
            used=parse_date(row[dm],year,month)
            merchant=' '.join(str(row[mm] or '').split())
            purpose=' '.join(str(row[pm] or '').split())
            value=amount(row[am])
            if not used or not merchant or merchant in {'계','합계'} or value is None:continue
            result.append({
                'source_key':'komipo','institution':'한국중부발전','cohort':'public_enterprise_leadership','role':'사장','department':'',
                'used_date':used,'used_time':'','merchant':merchant,'address':'','purpose':purpose,
                'people':people(row[nm]) if nm is not None and nm<len(row) else None,'amount':value,'source_amount_scale':1,
                'payment_method':' '.join(str(row[gm] or '').split()) if gm is not None and gm<len(row) else '',
                'source_category':'사장 업무추진비','source_url':source_url,'source_sheet':sheet,'source_row':ri,
                'row_id':f'komipo:{seq}:{sheet}:{ri}'
            })
    return result

def main():
    report=json.loads(DISCOVERY.read_text(encoding='utf-8'))
    reg=json.loads(REGISTRY.read_text(encoding='utf-8'))
    src=next((x for x in reg.get('sources',[]) if x.get('key')=='komipo'),None)
    if not src:return
    target_year=int(report.get('year') or datetime.now().year)
    years={target_year,target_year-1}
    pages=[]; posts={}; errors=[]
    for page_index in range(1,5):
        url=BASE+f'boardMain.do?mnCd={MN}&schTabCd={TAB}&pageIndex={page_index}'
        pages.append(url)
        try:raw,_=request(url);doc=raw.decode('utf-8',errors='replace')
        except Exception as e:errors.append(f'listing {page_index}: {type(e).__name__}: {e}');continue
        for m in re.finditer(r'<a\b([^>]*)>(.*?)</a>',doc,re.S|re.I):
            attrs=m.group(1);label=text(m.group(2))
            sm=re.search(r'board\.view\([\'\"]?(\d+)',attrs,re.I)
            if not sm or '업무추진비' not in label or '사장' not in label:continue
            ym=re.search(r'(20\d{2})\D{0,8}(1[0-2]|0?[1-9])\s*월',label)
            if not ym:continue
            y,mo=int(ym.group(1)),int(ym.group(2))
            if y in years:posts[sm.group(1)]=(label,y,mo,page_index)
    inline=[]
    for seq,(title,y,mo,page_index) in sorted(posts.items(),key=lambda kv:(kv[1][1],kv[1][2]),reverse=True):
        referer=BASE+f'boardMain.do?mnCd={MN}&schTabCd={TAB}&pageIndex={page_index}'
        pdata=urllib.parse.urlencode({'pageIndex':str(page_index),'mnCd':MN,'boardSeq':seq,'schTabCd':TAB}).encode()
        try:raw,_=request(BASE+f'boardView.do?mnCd={MN}',pdata,referer);doc=raw.decode('utf-8',errors='replace')
        except Exception as e:errors.append(f'detail {seq}: {type(e).__name__}: {e}');continue
        am=re.search(r"board\.download\('([^']+)'\s*,\s*'([^']+)'\)[^>]*>([^<]*(?:\.hwpx|\.hwp))",doc,re.I)
        if not am:
            # tolerate attributes between href and label
            am=re.search(r"board\.download\('([^']+)'\s*,\s*'([^']+)'\).*?>([^<]+)</a>",doc,re.I|re.S)
        if not am:errors.append(f'attachment missing {seq}');continue
        atch,file_sn,file_name=am.group(1),am.group(2),text(am.group(3))
        detail_url=BASE+f'boardView.do?mnCd={MN}#boardSeq={seq}'
        fields={'pageIndex':str(page_index),'mnCd':MN,'boardSeq':seq,'boardCd':'BRD_000065','atchFileId':atch,'fileSn':file_sn,'formNo':'','schTabCd':TAB}
        try:blob,_=request('https://www.komipo.co.kr/atch/fileDown.do',urllib.parse.urlencode(fields).encode(),BASE+f'boardView.do?mnCd={MN}')
        except Exception as e:errors.append(f'download {seq}: {type(e).__name__}: {e}');continue
        try:inline.extend(extract_rows(blob,y,mo,detail_url,seq))
        except Exception as e:errors.append(f'parse {seq}: {type(e).__name__}: {e}')
    entry={
        'key':'komipo','institution':'한국중부발전','cohort':'public_enterprise_leadership','default_role':'사장',
        'years':sorted(years),'pages':pages,'attachments':[],'inline_rows':inline,'errors':errors,'inline_replace':True,
        'parseable_attachments':len(posts),'status':'PARSEABLE_FOUND' if inline else ('FETCH_FAILED' if errors else 'NO_FILES_FOUND')
    }
    sources=report.get('sources') or []
    sources=[entry if x.get('key')=='komipo' else x for x in sources]
    if not any(x.get('key')=='komipo' for x in sources):sources.append(entry)
    report['sources']=sources
    DISCOVERY.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'posts':len(posts),'rows':len(inline),'merchants':len({x['merchant'] for x in inline}),'errors':errors[:5]},ensure_ascii=False))

if __name__=='__main__':main()
