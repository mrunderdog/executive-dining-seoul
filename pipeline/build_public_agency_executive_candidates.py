#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict,Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data"/"raw"/"public_agency_executive_expense.json"
DETAIL_RAW=ROOT/"data"/"raw"/"public_agency_detail_expense.json"
OUT=ROOT/"reports"/"public-agency-executive-candidates.json"
MD=ROOT/"reports"/"public-agency-executive-candidates.md"


def t(v): return " ".join(str(v or "").split()).strip()

def clean_merchant(v:str)->str:
    s=t(v)
    s=re.sub(r"\s+"," ",s)
    return s

def main():
    if not RAW.exists():
        raise SystemExit("raw file missing")
    d=json.loads(RAW.read_text(encoding="utf-8"))
    rows=list(d.get("rows") or [])
    if DETAIL_RAW.exists():
        dd=json.loads(DETAIL_RAW.read_text(encoding="utf-8"))
        rows.extend(dd.get("rows") or [])
    groups=defaultdict(list)
    for r in rows:
        m=clean_merchant(r.get("merchant"))
        if not m:
            continue
        groups[m].append(r)

    candidates=[]
    for merchant,rows in groups.items():
        agencies=sorted({t(r.get("agency_name")) for r in rows if t(r.get("agency_name"))})
        agency_ids=sorted({t(r.get("agency_id")) for r in rows if t(r.get("agency_id"))})
        visits=len(rows)
        spend=sum(int(r.get("amount") or 0) for r in rows)
        purposes=Counter(t(r.get("purpose")) for r in rows if t(r.get("purpose")))
        dates=[t(r.get("date")) for r in rows if t(r.get("date"))]
        score=visits*10+len(agencies)*15+min(spend/100000,25)
        candidates.append({
            "merchant":merchant,
            "visits":visits,
            "spend":spend,
            "institution_count":len(agencies),
            "institutions":agencies,
            "agency_ids":agency_ids,
            "score":round(score,1),
            "date_min":min(dates) if dates else "",
            "date_max":max(dates) if dates else "",
            "purpose_stats":[{"purpose":k,"visits":v} for k,v in purposes.most_common(8)],
            "recent":sorted(rows,key=lambda x:t(x.get("date")),reverse=True)[:12],
        })

    candidates.sort(key=lambda x:(x["score"],x["visits"],x["spend"]),reverse=True)
    out={
        "schema_version":1,
        "source":"ALIO 기관장 업무추진비",
        "candidate_count":len(candidates),
        "candidates":candidates,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md=[
      "# 공공기관 기관장 업무추진비 식당 후보",
      "",
      f"- 후보: {len(candidates)}개",
      "",
      "| 순위 | 식당/사용처 | 방문 | 기관 | 집행액 |",
      "|---:|---|---:|---:|---:|",
    ]
    for i,c in enumerate(candidates[:100],1):
        md.append(f"| {i} | {c['merchant']} | {c['visits']} | {c['institution_count']} | {c['spend']:,}원 |")
    MD.write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"candidate_count":len(candidates),"top":candidates[:10]},ensure_ascii=False))


if __name__=="__main__":
    main()
