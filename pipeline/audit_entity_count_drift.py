#!/usr/bin/env python3
"""Compare two published entity snapshots without changing public records."""
import argparse, json, subprocess, sys
from pathlib import Path

def snapshot(ref):
    p=subprocess.run(["git","archive",ref],stdout=subprocess.PIPE,check=True)
    import tarfile,io,tempfile
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tar:
            tar.extractall(tmp,filter="data")
        code="""from data_io import load_payload
from extra_published import merge_extra_published
from published_sources import merge_published_sources
from global_entities import merge_global_entities
import json
d=merge_global_entities(merge_extra_published(merge_published_sources(load_payload())))
print(json.dumps([{'entity_id':x.get('entity_id'),'source_keys':x.get('source_keys',[]),'name':x.get('name'),'address':x.get('address'),'origins':x.get('origins',[])} for x in d['records']],ensure_ascii=False))
"""
        r=subprocess.run([sys.executable,"-c",code],cwd=tmp,env={**__import__("os").environ,"PYTHONPATH":str(Path(tmp)/"pipeline")},capture_output=True,text=True,check=True)
        return json.loads(r.stdout)

def audit(old,new):
    oldkeys={k for r in old for k in r['source_keys']}
    newkeys={k for r in new for k in r['source_keys']}
    oldby={k:r for r in old for k in r['source_keys']}
    newby={k:r for r in new for k in r['source_keys']}
    lost=sorted(oldkeys-newkeys)
    appeared=sorted(newkeys-oldkeys)
    if lost:raise ValueError(f"published source keys disappeared: {lost[:12]}")
    moved=[{'source_key':k,'previous_entity':oldby[k]['entity_id'],'current_entity':newby[k]['entity_id'],'name':newby[k]['name'],'address':newby[k]['address']}
           for k in sorted(oldkeys&newkeys) if oldby[k]['entity_id']!=newby[k]['entity_id']]
    counts={}
    for r in new:
        for k in r['source_keys']:
            if k in oldby: counts.setdefault(r['entity_id'],set()).add(oldby[k]['entity_id'])
    new_group={r['entity_id']:r for r in new}
    suspected=[{'entity_id':k,'previous_entities':sorted(v),'merged_name':new_group[k]['name'],
                'merged_address':new_group[k]['address'],'source_keys':new_group[k]['source_keys']}
               for k,v in counts.items() if len(v)>1]
    return {'previous_total':len(old),'current_total':len(new),'delta':len(new)-len(old),'lost_source_keys':lost,'new_source_keys':appeared,'moved_source_keys':moved,'merged_previous_entities':suspected,'explanation':'No original source key lost' if not lost else 'SOURCE KEY LOSS'}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--before",required=True)
    ap.add_argument("--after",default="HEAD")
    ap.add_argument("--output",default="reports/p4-entity-count-drift.json")
    args=ap.parse_args()
    d=audit(snapshot(args.before),snapshot(args.after))
    Path(args.output).parent.mkdir(exist_ok=True,parents=True)
    Path(args.output).write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v if not isinstance(v,list) else len(v) for k,v in d.items()},ensure_ascii=False))
if __name__=="__main__":main()
