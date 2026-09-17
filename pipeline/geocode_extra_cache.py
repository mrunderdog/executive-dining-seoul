#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from extra_published import central_records, legislator_records
from geocode_cache import load_cache, save_cache, fingerprint, query_plan, resolve, GEOCODER_VERSION, POLICY_VERSION

def main():
    records=central_records()+legislator_records();cache=load_cache();items=cache.setdefault('records',{});ok=failed=requests=0
    todo=[]
    for r in records:
        key=f"{r.get('name','')}|{r.get('origin','')}";fp=fingerprint(r);old=items.get(key) if isinstance(items.get(key),dict) else {}
        if old.get('fingerprint')==fp and old.get('geocoder_version')==GEOCODER_VERSION and (old.get('failed') or isinstance(old.get('lat'),(int,float))):continue
        plan=query_plan(r)
        if plan:todo.append((key,r,fp,plan))
    print(f'extra geocoder records={len(records)} candidates={len(todo)}')
    for i,(key,r,fp,plan) in enumerate(todo,1):
        result,tried,nreq=resolve(r,plan);requests+=nreq;stamp={'fingerprint':fp,'geocoder_version':GEOCODER_VERSION,'policy_version':POLICY_VERSION,'tried_queries':tried,'updated_at':datetime.now(timezone.utc).isoformat(timespec='seconds')}
        if result:
            result.update(stamp);items[key]=result;ok+=1;print(f'[{i}/{len(todo)}] OK {key} -> {result["lat"]:.6f},{result["lon"]:.6f}')
        else:
            items[key]={'failed':True,**stamp};failed+=1;print(f'[{i}/{len(todo)}] NO_MATCH {key}')
        save_cache(cache)
    save_cache(cache);print(json.dumps({'records':len(records),'processed':len(todo),'requests':requests,'ok':ok,'failed':failed},ensure_ascii=False))
if __name__=='__main__':main()
