#!/usr/bin/env python3
"""P2 gate for reproducible council release: original transaction protection and ranking audit."""
from __future__ import annotations
import argparse
import json
import hashlib
import math
import sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCES={"ansan":279,"hwaseong":237}

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":"),default=str)

def get_payload():
    from data_io import load_payload
    from published_sources import merge_published_sources
    from extra_published import merge_extra_published
    from global_entities import merge_global_entities
    return merge_global_entities(merge_extra_published(merge_published_sources(load_payload())))

def score_sample(row):
    return {"executive": (row.get("executive") or {}).get("score"),
            "destination": (row.get("destination") or {}).get("score"),
            "consensus": (row.get("cross_institution") or {}).get("score"),
            "visits": (row.get("evidence") or {}).get("visits"),
            "spend": (row.get("evidence") or {}).get("spend"),
            "months": (row.get("evidence") or {}).get("months")}

def entity_snapshot():
    return [{"entity_id":str(x.get("entity_id") or ""),
             "source_keys":sorted(str(k) for k in (x.get("source_keys") or [])),
             "name":x.get("name"),"address":x.get("address"),
             "origins":x.get("origins") or [],
             "score":score_sample(x)}
            for x in get_payload().get("records",[])]

def source_snapshot(source):
    p=ROOT/"data"/"raw"/f"{source}_expense.json"
    d=json.loads(p.read_text(encoding="utf-8"))
    rows=d.get("rows") or []
    files=d.get("files") or []
    return {"rows_count":len(rows),"files_count":len(files),
            "rows":{str(r.get("row_id")):hashlib.sha256(canonical(r).encode()).hexdigest() for r in rows},
            "row_ids":[str(r.get("row_id")) for r in rows],
            "files":{str(f.get("url")):canonical(f) for f in files}}

def snapshot():
    return {"sources":{s:source_snapshot(s) for s in SOURCES},
            "entities":entity_snapshot()}

def checks(baseline):
    from audit_entity_count_drift import audit
    now=snapshot()
    problems=[]
    changes={}
    for s,expected in SOURCES.items():
        old=baseline["sources"][s]
        new=now["sources"][s]
        oldids=set(old["rows"])
        newids=set(new["rows"])
        added=newids-oldids
        lost=oldids-newids
        modified=[rid for rid in oldids&newids if old["rows"][rid]!=new["rows"][rid]]
        duplicates=len(new["row_ids"])-len(newids)
        removed_files=set(old["files"])-set(new["files"])
        changed_files=[u for u in old["files"].keys() & new["files"].keys() if old["files"][u]!=new["files"][u]]
        changes[s]={"baseline":old["rows_count"],"after":new["rows_count"],"added_rows":len(added),
                    "expected_new":expected,"lost_rows":len(lost),"modified_rows":len(modified),
                    "duplicate_row_ids":duplicates,"removed_files":len(removed_files),"modified_old_files":len(changed_files),
                    "new_files":new["files_count"]-old["files_count"]}
        if len(added)!=expected:problems.append(f"{s}: expected {expected} genuinely new rows, got {len(added)}")
        if lost:problems.append(f"{s}: original row IDs lost: {sorted(lost)[:5]}")
        if modified:problems.append(f"{s}: original row content changed: {modified[:5]}")
        if duplicates:problems.append(f"{s}: duplicate row IDs: {duplicates}")
        if removed_files or changed_files:problems.append(f"{s}: committed original file lineage removed/changed")
    old_e=baseline["entities"]
    new_e=now["entities"]
    old_no_score=[{k:v for k,v in e.items() if k!="score"} for e in old_e]
    new_no_score=[{k:v for k,v in e.items() if k!="score"} for e in new_e]
    try:
        drift=audit(old_no_score,new_no_score)
    except ValueError as e:
        problems.append(str(e))
        drift={"lost_source_keys":["AUDIT_FAILED"],"moved_source_keys":[],"merged_previous_entities":[],"new_source_keys":[]}
    oldby={e["entity_id"]:e for e in old_e}
    newby={e["entity_id"]:e for e in new_e}
    changed_scores=[]
    non_source_changes=[]
    missing_ids=set(oldby)-set(newby)
    for eid in sorted(set(oldby)&set(newby)):
        former=oldby[eid]; current=newby[eid]
        if former["score"]==current["score"]:
            continue
        change={"entity_id":eid,"name":current["name"],"old":former["score"],"new":current["score"]}
        changed_scores.append(change)
        if former["source_keys"]==current["source_keys"]:
            # A score can change within a source even when its merchant source key stays constant.
            # Only guard unrelated origins (no newly refreshed institution among the record's origins).
            origins=" ".join(former["origins"]+current["origins"])
            if not any(x in origins for x in ("안산시","화성시")):
                non_source_changes.append(change)
    if non_source_changes:
        problems.append(f"unrelated institution records changed scores: {len(non_source_changes)}")
    for e in new_e:
        for key,value in e["score"].items():
            if isinstance(value,(int,float)) and (not math.isfinite(value) or value<0):
                problems.append(f"invalid {key} score for {e['name']}")
    # Merges of multiple pre-existing entities at conflicting, verified street addresses are unsafe.
    from global_entities import canonical_address
    for group in drift.get("merged_previous_entities",[]):
        addresses={canonical_address(oldby[eid]["address"]) for eid in group["previous_entities"]
                   if eid in oldby and oldby[eid].get("address")}
        if len(addresses)>1:
            problems.append(f"potential unsafe physical venue merge: {group['entity_id']}")
    if missing_ids and not drift.get("moved_source_keys"):
        problems.append(f"disappeared entity IDs without documented source-key movement: {sorted(missing_ids)[:5]}")
    return {"status":"PASS" if not problems else "FAIL","sources":changes,
            "global_before":len(old_e),"global_after":len(new_e),
            "new_entity_source_keys":len(drift.get("new_source_keys",[])),
            "lost_entity_source_keys":len(drift.get("lost_source_keys",[])),
            "moved_entity_source_keys":len(drift.get("moved_source_keys",[])),
            "merged_previous_entities":drift.get("merged_previous_entities",[]),
            "changed_scores_count":len(changed_scores),"changed_scores_examples":changed_scores[:30],
            "unrelated_score_changes":non_source_changes[:10],"problems":problems}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=["baseline","verify"])
    ap.add_argument("--baseline",default="/tmp/p2-ansan-hwaseong-baseline.json")
    ap.add_argument("--output",default="reports/p2-ansan-hwaseong-release-audit.json")
    args=ap.parse_args()
    if args.mode=="baseline":
        obj=snapshot()
        Path(args.baseline).write_text(canonical(obj),encoding="utf-8")
        print(canonical({"phase":"baseline","sources":{s:{"rows":v["rows_count"],"files":v["files_count"]} for s,v in obj["sources"].items()},
                         "entity_count":len(obj["entities"])}))
        return
    baseline=json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    report=checks(baseline)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if report["status"]!="PASS":
        sys.exit(1)

if __name__=="__main__": main()
