#!/usr/bin/env python3
"""Read-only month-boundary comparison for source-printed Hwaseong expenses.

A late-month official source may repeat an earlier-month record. Only a
complete match on original economic identity and an independently in-period
official source can establish duplication. Otherwise remain strict QA HOLD.
"""
import json
from collections import defaultdict,Counter
from pathlib import Path
from reconcile_gimpo_sources import economic_key,within_declared_period

ROOT=Path(__file__).resolve().parents[1]
raw=ROOT/"data/raw/hwaseong_expense.json"
data=json.loads(raw.read_text(encoding="utf-8"))
rows=data.get("rows",[])
in_period=defaultdict(list)
for row in rows:
    if within_declared_period(row):
        in_period[economic_key(row)].append(row)
items=[]
for row in rows:
    if within_declared_period(row):
        continue
    near=[r for r in rows if (
        r.get("used_date"),r.get("merchant"),r.get("amount"))==(
        row.get("used_date"),row.get("merchant"),row.get("amount"))
        and r.get("row_id")!=row.get("row_id")]
    exact=[r for r in in_period.get(economic_key(row),[])
           if r.get("source_attachment_url")!=row.get("source_attachment_url")]
    decision=("VERIFIED_IDENTICAL_CROSS_FILE_DUPLICATE" if len(exact)==1
              else "HOLD_ORIGINAL_DATE_OR_PERIOD")
    items.append({
        "status":decision,"row_id":row.get("row_id"),"used_date":row.get("used_date"),
        "source_period":row.get("source_period"),"source_sheet":row.get("source_sheet"),
        "source_row":row.get("source_row"),"source_url":row.get("source_attachment_url"),
        "merchant":row.get("merchant"),"amount":row.get("amount"),
        "role":row.get("role"),"purpose":row.get("purpose"),
        "payment_method":row.get("payment_method"),
        "exact_matches":[{"row_id":r.get("row_id"),"source_url":r.get("source_attachment_url"),
                          "source_period":r.get("source_period"),"source_row":r.get("source_row")}
                         for r in exact[:4]],
        "near_matches":[{"row_id":r.get("row_id"),"purpose":r.get("purpose"),
                         "role":r.get("role"),"source_url":r.get("source_attachment_url"),
                         "source_period":r.get("source_period")} for r in near[:4]],
    })
result={
    "source":"hwaseong",
    "full_source_rows":len(rows),
    "invalid_original_rows":len(items),
    "counts":dict(Counter(x["status"] for x in items)),
    "records":items,
    "policy":"Exact cross-file duplication requires fully identical economic fields and independently in-period official source; all other entries remain HOLD."
}
dest=ROOT/"reports/p1-ansan-hwaseong-qa/hwaseong-period-cross-file.json"
dest.parent.mkdir(parents=True,exist_ok=True)
dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PERIOD_CROSS_FILE",json.dumps(result,ensure_ascii=False)[:15000],flush=True)
