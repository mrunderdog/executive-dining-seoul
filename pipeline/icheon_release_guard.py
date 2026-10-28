#!/usr/bin/env python3
"""Fail-closed Icheon June 2026 release gate; snapshots existing source and global entities.

The official chair PDF contains one malformed 2026-16-17 date. It is excluded,
never guessed as June 17. Only 45 fully verified rows are accepted (42+3).
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from p2_release_audit import source_snapshot, entity_snapshot, canonical
from audit_entity_count_drift import audit
from global_entities import canonical_address

ROOT=Path(__file__).resolve().parents[1]
NEW_FILES={
    "https://council.icheon.go.kr/gtb_download.php?fid=4769&gtid=chujin":42,
    "https://council.icheon.go.kr/gtb_download.php?fid=4770&gtid=chujin":3,
}

def snapshot()->dict:
    return {"source":source_snapshot("icheon"),"entities":entity_snapshot()}

def verify(old:dict)->dict:
    now=snapshot()
    before=old["source"]
    after=now["source"]
    old_ids=set(before["rows"]); new_ids=set(after["rows"])
    added=new_ids-old_ids
    removed=old_ids-new_ids
    changed=[i for i in old_ids&new_ids if before["rows"][i]!=after["rows"][i]]
    repeated=len(after["row_ids"])-len(new_ids)
    old_files=set(before["files"])
    new_files=set(after["files"])-old_files
    removed_files=old_files-set(after["files"])
    changed_old_files=[url for url in old_files & set(after["files"]) if before["files"][url]!=after["files"][url]]
    raw=json.loads((ROOT/"data/raw/icheon_expense.json").read_text(encoding="utf-8"))
    source_rows=[r for r in raw.get("rows",[]) if r.get("row_id") in added]
    rows_by_file=Counter(r.get("source_attachment_url") for r in source_rows)
    new_file_docs=[f for f in raw.get("files",[]) if f.get("url") in NEW_FILES]
    errors=[]
    if len(added)!=45:errors.append(f"expected exactly 45 newly verified rows, got {len(added)}")
    if len(after["row_ids"])!=len(after["rows"]):errors.append("row ID count mismatch")
    if removed:errors.append(f"historical row IDs removed: {sorted(removed)[:6]}")
    if changed:errors.append(f"historical transaction contents changed: {changed[:6]}")
    if repeated:errors.append(f"duplicate row IDs: {repeated}")
    if removed_files or changed_old_files:errors.append("original official attachment identity/metadata changed")
    if new_files!=set(NEW_FILES):errors.append(f"unexpected new official attachments: {sorted(new_files)}")
    if dict(rows_by_file)!=NEW_FILES:errors.append(f"unexpected verified row/file counts: {dict(rows_by_file)}")
    for row in source_rows:
        date=str(row.get("used_date") or "")
        amount=row.get("amount")
        if not date.startswith("2026-06-") or not isinstance(amount,(int,float)) or not 0<amount<50_000_000:
            errors.append(f"invalid date or amount in new row {row.get('row_id')}")
        if row.get("source_key")!="icheon" or row.get("source_attachment_url") not in NEW_FILES:
            errors.append(f"unexpected source for row {row.get('row_id')}")
        if row.get("source_attachment_url","").find("fid=4770")>=0 and row.get("role"):
            errors.append(f"improper role attribution on shared common expense: {row.get('row_id')}")
    invalid=[]
    for f in new_file_docs:
        for sheet in f.get("sheets",[]):
            for item in sheet.get("invalid_date_examples",[]):
                invalid.append({"url":f["url"],"page":sheet.get("sheet"), **item})
    if len(invalid)!=1 or invalid[0].get("observed_date")!="2026-16-17":
        errors.append(f"unexpected invalid-date quarantine: {invalid}")
    before_e=[{k:v for k,v in e.items() if k!="score"} for e in old["entities"]]
    after_e=[{k:v for k,v in e.items() if k!="score"} for e in now["entities"]]
    try:
        drift=audit(before_e,after_e)
    except ValueError as e:
        errors.append(str(e))
        drift={"lost_source_keys":["AUDIT_FAILED"],"new_source_keys":[],"moved_source_keys":[],
               "merged_previous_entities":[]}
    oldby={e["entity_id"]:e for e in old["entities"]}
    newby={e["entity_id"]:e for e in now["entities"]}
    score_changes=[]; unrelated_changes=[]
    for eid in sorted(set(oldby)&set(newby)):
        a,b=oldby[eid],newby[eid]
        if a["score"]!=b["score"]:
            line={"entity_id":eid,"name":b["name"],"before":a["score"],"after":b["score"]}
            score_changes.append(line)
            origins=" ".join(a["origins"]+b["origins"])
            if "이천시" not in origins:unrelated_changes.append(line)
    if unrelated_changes:errors.append(f"unrelated institution rankings changed: {len(unrelated_changes)}")
    for entity in now["entities"]:
        for key,value in entity["score"].items():
            if isinstance(value,(int,float)) and (not math.isfinite(value) or value<0):
                errors.append(f"invalid {key} score for {entity['name']}")
    for merged in drift.get("merged_previous_entities",[]):
        addresses={canonical_address(oldby[eid]["address"])
                   for eid in merged.get("previous_entities",[])
                   if eid in oldby and oldby[eid].get("address")}
        if len(addresses)>1:errors.append(f"unsafe physical restaurant merge: {merged['entity_id']}")
    report={"status":"PASS" if not errors else "FAIL","source":"icheon",
            "baseline_rows":before["rows_count"],"new_total_rows":after["rows_count"],
            "verified_new_rows":len(added),"rows_by_new_official_pdf":dict(rows_by_file),
            "lost_prior_rows":len(removed),"changed_prior_rows":len(changed),
            "duplicate_row_ids":repeated,"lost_prior_files":len(removed_files),
            "changed_prior_files":len(changed_old_files),
            "quarantined_official_invalid_date_rows":invalid,
            "entities_before":len(old["entities"]),"entities_after":len(now["entities"]),
            "lost_entity_source_keys":len(drift.get("lost_source_keys",[])),
            "new_entity_source_keys":len(drift.get("new_source_keys",[])),
            "moved_entity_source_keys":len(drift.get("moved_source_keys",[])),
            "merged_previous_entities":drift.get("merged_previous_entities",[]),
            "changed_existing_scores":score_changes[:40],
            "unrelated_score_changes":unrelated_changes[:10],"errors":errors}
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=["baseline","verify"])
    ap.add_argument("--baseline",default="/tmp/icheon-source-and-entity-baseline.json")
    ap.add_argument("--output",default="reports/icheon-release-audit.json")
    args=ap.parse_args()
    if args.mode=="baseline":
        old=snapshot()
        Path(args.baseline).write_text(canonical(old),encoding="utf-8")
        print(json.dumps({"phase":"baseline","rows":old["source"]["rows_count"],"files":old["source"]["files_count"],
                          "entities":len(old["entities"])},ensure_ascii=False))
        return
    old=json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    report=verify(old)
    out=ROOT/args.output
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if report["status"]!="PASS":raise SystemExit(1)
if __name__=="__main__":main()
