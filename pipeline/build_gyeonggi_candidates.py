#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data"/"raw"/"gyeonggi_province_expense.json"
REPORTS=ROOT/"reports"

MEAL_WORDS=("간담","식사","오찬","만찬","조찬","회의","협의","논의","격려","소통","현안","관계자","업무")
EXCLUDE_WORDS=("주유","주차","택시","교통","인쇄","문구","사무","온라인","쿠팡","네이버","다이소","기념품","상품권","화환","꽃","카페","커피","스타벅스","이디야","베이커리","빵")


def t(v):
    return " ".join(str(v or "").split()).strip()


def looks_meal(r):
    merchant=t(r.get("merchant")); purpose=t(r.get("purpose"))
    if not merchant: return False
    s=f"{merchant} {purpose}"
    if any(x in s for x in EXCLUDE_WORDS): return False
    return any(x in purpose for x in MEAL_WORDS)


def score(visits,departments,months,spend):
    repeat=min(math.log1p(visits)/math.log1p(20),1)
    breadth=min(math.log1p(departments)/math.log1p(12),1)
    persistence=min(months/8,1)
    spend_norm=min(math.log1p(max(spend,0))/math.log1p(8_000_000),1)
    return round(100*(.35*repeat+.35*breadth+.18*persistence+.12*spend_norm),1)


def main():
    if not RAW.exists(): raise SystemExit(f"missing {RAW}")
    d=json.loads(RAW.read_text(encoding="utf-8"))
    rows=[r for r in d.get("rows",[]) if r.get("date_quality")=="in_period" and looks_meal(r)]
    groups=defaultdict(list)
    for r in rows:
        name=t(r.get("merchant"))
        if name: groups[name].append(r)

    out=[]
    for name,items in groups.items():
        departments=sorted({t(r.get("department") or r.get("role")) for r in items if t(r.get("department") or r.get("role"))})
        months=sorted({t(r.get("used_date"))[:7] for r in items if re.match(r"20\d{2}-\d{2}",t(r.get("used_date")))})
        visits=len(items)
        spend=sum(int(r.get("amount") or 0) for r in items)
        addresses=[t(r.get("address")) for r in items if t(r.get("address"))]
        address=Counter(addresses).most_common(1)[0][0] if addresses else ""
        purposes=Counter(t(r.get("purpose")) for r in items if t(r.get("purpose")))
        dept_stats=Counter(t(r.get("department") or r.get("role")) for r in items if t(r.get("department") or r.get("role")))
        dates=sorted(t(r.get("used_date")) for r in items if t(r.get("used_date")))
        out.append({
            "merchant":name,
            "address":address,
            "score":score(visits,len(departments),len(months),spend),
            "visits":visits,
            "department_count":len(departments),
            "departments":departments,
            "months":len(months),
            "spend":spend,
            "date_min":dates[0] if dates else "",
            "date_max":dates[-1] if dates else "",
            "department_stats":[{"department":k,"visits":v} for k,v in dept_stats.most_common(15)],
            "purpose_stats":[{"text":k,"count":v} for k,v in purposes.most_common(8)],
            "recent":[{
                "date":t(r.get("used_date")),"time":t(r.get("used_time")),
                "department":t(r.get("department") or r.get("role")),
                "amount":int(r.get("amount") or 0),"people":int(r.get("people") or 0),
                "purpose":t(r.get("purpose")),"source":t(r.get("source_post_url")),
            } for r in sorted(items,key=lambda x:(t(x.get("used_date")),t(x.get("used_time"))),reverse=True)[:10]],
        })
    eligible=[x for x in out if x["visits"]>=3 and x["department_count"]>=2 and x["months"]>=2 and x["score"]>=45]
    eligible.sort(key=lambda x:(x["score"],x["department_count"],x["visits"],x["spend"]),reverse=True)
    payload={
        "source":"gyeonggi_province","cohort":"regional_executive",
        "entity_count":len(out),"eligible_count":len(eligible),
        "publication_status":"staged_not_published",
        "candidates":eligible[:150],
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS/"gyeonggi-province-candidates.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    md=[
        "# Gyeonggi Province Executive Dining candidates","",
        f"- Meal-like rows: **{len(rows)}**",
        f"- Merchant entities: **{len(out)}**",
        f"- Eligible candidates: **{len(eligible)}**","",
        "| # | Merchant | Score | Visits | Departments | Months | Spend | Address |",
        "|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for i,x in enumerate(eligible[:100],1):
        md.append(f"| {i} | {x['merchant'].replace('|','/')} | {x['score']:.1f} | {x['visits']} | {x['department_count']} | {x['months']} | {x['spend']:,} | {x['address'].replace('|','/')} |")
    (REPORTS/"gyeonggi-province-candidates.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"meal_rows":len(rows),"entities":len(out),"eligible":len(eligible),"top":eligible[:5]},ensure_ascii=False))


if __name__=="__main__":
    main()
