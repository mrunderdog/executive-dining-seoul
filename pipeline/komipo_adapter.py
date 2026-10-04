#!/usr/bin/env python3
from __future__ import annotations
import html, io, re, ssl, urllib.parse, urllib.request, zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

UA="ExecutiveDiningSeoul/2.1 (+https://github.com/mrunderdog/executive-dining-seoul)"
BASE="https://www.komipo.co.kr/kor/board/BRD_000065/"
TAB="KH041301"

def _decode(raw,charset=None):
    for c in (charset,"utf-8","cp949","euc-kr"):
        if not c: continue
        try:return raw.decode(c)
        except Exception:pass
    return raw.decode("utf-8",errors="replace")

def _request(url,data=None,referer=None,binary=False):
    ctx=ssl._create_unverified_context()
    headers={"User-Agent":UA,"Accept":"*/*","Referer":referer or url}
    if data is not None:headers["Content-Type"]="application/x-www-form-urlencoded"
    req=urllib.request.Request(url,data=data,headers=headers)
    with urllib.request.urlopen(req,timeout=35,context=ctx) as r:
        raw=r.read()
        return raw if binary else _decode(raw,r.headers.get_content_charset())

def _local(tag):return tag.rsplit('}',1)[-1].split(':')[-1].lower()

def _tables(blob):
    if not zipfile.is_zipfile(io.BytesIO(blob)):return []
    z=zipfile.ZipFile(io.BytesIO(blob));out=[]
    for name in z.namelist():
        if not (name.lower().endswith('.xml') and 'section' in name.lower()):continue
        try:root=ET.fromstring(z.read(name))
        except Exception:continue
        for tbl in (x for x in root.iter() if _local(x.tag)=='tbl'):
            rows=[]
            for tr in (x for x in tbl.iter() if _local(x.tag)=='tr'):
                cells=[]
                for tc in [x for x in list(tr) if _local(x.tag)=='tc']:
                    vals=[n.text for n in tc.iter() if _local(n.tag)=='t' and n.text]
                    cells.append(' '.join(' '.join(vals).split()))
                if cells:rows.append(cells)
            if rows:out.append(rows)
    return out

def _ym(text):
    m=re.search(r'(20\d{2})\D{0,5}(1[0-2]|0?[1-9])\s*월',text or '')
    return (int(m.group(1)),int(m.group(2))) if m else (None,None)

def _date(text,default_year):
    nums=[int(x) for x in re.findall(r'\d+',text or '')]
    if len(nums)>=3:
        y=nums[0];y=2000+y if y<100 else y;m,d=nums[1],nums[2]
    elif len(nums)>=2:y=default_year;m,d=nums[0],nums[1]
    else:return ''
    try:return datetime(y,m,d).date().isoformat()
    except Exception:return ''

def _clean_html(s):return ' '.join(html.unescape(re.sub(r'<[^>]+>',' ',s or '')).split())

def discover_komipo(src,year,detail_limit=30):
    base=(src.get('listing_urls') or [BASE+'boardMain.do?mnCd=FN010712&schTabCd='+TAB+'&pageIndex=1'])[0]
    years={year,year-1}
    out={"key":src["key"],"institution":src["institution"],"cohort":src.get("cohort","public_enterprise_leadership"),"default_role":src.get("default_role","사장"),"years":sorted(years),"pages":[],"attachments":[],"inline_rows":[],"errors":[],"inline_replace":True}
    parsed=urllib.parse.urlsplit(base);q0=dict(urllib.parse.parse_qsl(parsed.query,keep_blank_values=True));posts={}
    for page_no in range(1,6):
        q=dict(q0);q['pageIndex']=str(page_no);q['schTabCd']=TAB
        listing=urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urllib.parse.urlencode(q),parsed.fragment))
        try:doc=_request(listing)
        except Exception as e:out['errors'].append(f"listing {listing}: {type(e).__name__}: {e}");continue
        out['pages'].append(listing)
        for m in re.finditer(r'<a\b[^>]*href=["\']javascript:board\.view\(["\']?(\d+)["\']?\);?["\'][^>]*>(.*?)</a>',doc,re.S|re.I):
            seq=m.group(1);title=_clean_html(m.group(2));y,mo=_ym(title)
            if y not in years or '업무추진비' not in title:continue
            if not re.search(r'(^|[^부본])사장\s*업무추진비',title):continue
            posts[seq]=(title,y,mo)
    detail_url=urllib.parse.urljoin(base,'boardView.do?mnCd=FN010712');download_url=urllib.parse.urljoin(base,'/atch/fileDown.do')
    ordered=sorted(posts.items(),key=lambda x:(x[1][1] or 0,x[1][2] or 0),reverse=True)[:detail_limit]
    for seq,(title,y,mo) in ordered:
        form={'pageIndex':'1','mnCd':'FN010712','boardSeq':seq,'boardCd':'BRD_000065','atchFileId':'','fileSn':'','formNo':'','schTabCd':TAB}
        try:doc=_request(detail_url,urllib.parse.urlencode(form).encode(),base)
        except Exception as e:out['errors'].append(f"detail {seq}: {type(e).__name__}: {e}");continue
        out['pages'].append(base+'#boardSeq='+seq);attachment=None
        for m in re.finditer(r'<a\b[^>]*href=["\']javascript:board\.download\(["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\);?["\'][^>]*>(.*?)</a>',doc,re.S|re.I):
            label=_clean_html(m.group(3))
            if '업무추진비' in label and label.lower().endswith('.hwpx'):
                attachment=(m.group(1),m.group(2),label);break
        if not attachment:continue
        atch,file_sn,label=attachment;df=dict(form);df.update({'atchFileId':atch,'fileSn':file_sn})
        try:blob=_request(download_url,urllib.parse.urlencode(df).encode(),detail_url,binary=True)
        except Exception as e:out['errors'].append(f"download {seq}: {type(e).__name__}: {e}");continue
        out['attachments'].append({'text':label,'url':base+'#file='+atch+'-'+file_sn,'year':y,'month':mo,'parent':base+'#boardSeq='+seq,'attachment_id':atch+'|'+file_sn})
        for table in _tables(blob):
            hi=None;headers=[]
            for i,row in enumerate(table):
                joined=' '.join(row)
                if '사용일자' in joined and '사용처' in joined and '집행금액' in joined:hi=i;headers=row;break
            if hi is None:continue
            norm=[''.join(x.split()) for x in headers]
            def idx(term):return next((i for i,x in enumerate(norm) if term in x),None)
            di,pi,mi,ti,ci,ni,ai=idx('사용일자'),idx('집행내역'),idx('사용처'),idx('집행대상자'),idx('집행구분'),idx('인원'),idx('집행금액')
            if None in (di,pi,mi,ai):continue
            for ri,row in enumerate(table[hi+1:],start=hi+2):
                if len(row)<=max(di,pi,mi,ai):continue
                merchant=' '.join(row[mi].split());used=_date(row[di],y)
                if not merchant or merchant in ('계','합계') or not used:continue
                am=re.search(r'-?\d+(?:\.\d+)?',row[ai].replace(',',''));amount=int(round(float(am.group()))) if am else None
                people=None
                if ni is not None and ni<len(row):
                    pm=re.search(r'\d+',row[ni]);people=int(pm.group()) if pm else None
                out['inline_rows'].append({'source_key':src['key'],'institution':src['institution'],'cohort':src.get('cohort','public_enterprise_leadership'),'role':src.get('default_role','사장'),'department':'','used_date':used,'used_time':'','merchant':merchant,'address':'','purpose':' '.join(row[pi].split()),'people':people,'amount':amount,'source_amount_scale':1,'payment_method':(' '.join(row[ci].split()) if ci is not None and ci<len(row) else ''),'source_category':'사장 업무추진비','source_url':base+'#boardSeq='+seq,'source_sheet':label,'source_row':ri,'target':(' '.join(row[ti].split()) if ti is not None and ti<len(row) else '')})
    out['parseable_attachments']=len(out['attachments'])
    out['status']='PARSEABLE_FOUND' if out['inline_rows'] else ('FETCH_FAILED' if out['errors'] else 'NO_FILES_FOUND')
    return out
