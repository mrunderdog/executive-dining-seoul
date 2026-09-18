#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data"/"raw"/"incheon_province_expense.json"
REPORTS=ROOT/"reports"

MEAL_WORDS=("간담","식사","오찬","만찬","조찬","회의","협의","논의","격려","소통","현안","관계자","업무")
EXCLUDE_WORDS=("주유","주차","택시","교통","인쇄","문구","사무","온라인","쿠팡","네이버","다이소","기념품","상품권","화환","꽃","카페","커피","스타벅스","이디야","베이커리","빵","구내식당","편의점","마트")


def t(v): return " ".join(str(v or "").split()).strip()


def looks_meal(r):
    merchant=t(r.get("merchant")); purpose=t(r.get("purpose"))
    if not merchant: return False
    s=f"{merchant} {purpose}"
    if any(x in s for x in EXCLUDE_WORDS): return False
    return any(x in purpose for x in MEAL_WORDS) or any(x in t(r.get("role")) for x in ("시장","부시장"))


def role_weight(role):
    s=t(role)
    if "시장" in s and "부시장" not in s: return 1.0
    if "부시장" in s: return .9
    if any(x in s for x in ("실장","국장","과장")): return .65
    return .5


def score(visits,roles,months,weight,spend):
    repeat=min(math.log1p(visits)/math.log1p(10),1)
    breadth=min(roles/4,1)
    persistence=min(months/6,1)
    spend_norm=min(math.log1p(max(spend,0))/math.log1p(5_000_000),1)
    return round(100*(.30*repeat+.18*breadth+.20*persistence+.22*weight+.10*spend_norm),1)


def main():
    if not RAW.exists(): raise SystemExit(f"missing {RAW}")
    d=json.loads(RAW.read_text(encoding="utf-8"))
    rows=[r for r in d.get("rows",[]) if r.get("date_quality")=="in_period" and looks_meal(r)]
    groups=defaultdict(list)
    for r in rows:
        key=(t(r.get("merchant")),t(r.get("address")))
        if key[0]: groups[key].append(r)

    out=[]
    for (name,address),items in groups.items():
        roles=sorted({t(r.get("role") or r.get("department")) for r in items if t(r.get("role") or r.get("department"))})
        months=sorted({t(r.get("used_date"))[:7] for r in items if re.match(r"20\d{2}-\d{2}",t(r.get("used_date")))})
        visits=len(items); spend=sum(int(r.get("amount") or 0) for r in items)
        weight=max([role_weight(r.get("role")) for r in items] or [.5])
        mayor_visits=sum(1 for r in items if "시장" in t(r.get("role")) and "부시장" not in t(r.get("role")))
        vice_mayor_visits=sum(1 for r in items if "부시장" in t(r.get("role")))
        role_stats=Counter(t(r.get("role") or r.get("department")) or "직위 미상" for r in items)
        purposes=Counter(t(r.get("purpose")) for r in items if t(r.get("purpose")))
        dates=sorted(t(r.get("used_date")) for r in items if t(r.get("used_date")))
        out.append({
            "merchant":name,
            "address":address,
            "score":score(visits,len(roles),len(months),weight,spend),
            "visits":visits,
            "role_count":len(roles),
            "roles":roles,
            "months":len(months),
            "spend":spend,
            "senior_weight":weight,
            "mayor_visits":mayor_visits,
            "vice_mayor_visits":vice_mayor_visits,
            "date_min":dates[0] if dates else "",
            "date_max":dates[-1] if dates else "",
            "role_stats":[{"role":k,"visits":v} for k,v in role_stats.most_common(12)],
            "purpose_stats":[{"text":k,"count":v} for k,v in purposes.most_common(8)],
            "recent":[{
                "date":t(r.get("used_date")),"time":t(r.get("used_time")),
                "role":t(r.get("role") or r.get("department")),
                "amount":int(r.get("amount") or 0),"people":int(r.get("people") or 0),
                "purpose":t(r.get("purpose")),
                "source":t(r.get("source_post_url") or r.get("source_url")),
            } for r in sorted(items,key=lambda x:(t(x.get("used_date")),t(x.get("used_time"))),reverse=True)[:10]],
        })

    eligible=[x for x in out if x["visits"]>=2 and x["months"]>=1 and x["score"]>=45 and (x["mayor_visits"]+x["vice_mayor_visits"]>=1 or x["role_count"]>=2)]
    eligible.sort(key=lambda x:(x["score"],x["mayor_visits"]+x["vice_mayor_visits"],x["visits"],x["spend"]),reverse=True)

    payload={
        "source":"incheon_province","cohort":"regional_executive",
        "entity_count":len(out),"eligible_count":len(eligible),
        "publication_status":"staged_not_published",
        "candidates":eligible[:150],
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS/"incheon-province-candidates.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    md=[
        "# Incheon Metropolitan Government Executive Dining candidates","",
        f"- Meal-like rows: **{len(rows)}**",
        f"- Merchant entities: **{len(out)}**",
        f"- Eligible candidates: **{len(eligible)}**","",
        "| # | Merchant | Score | Visits | Mayor | Vice mayor | Roles | Months | Spend |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for i,x in enumerate(eligible[:100],1):
        md.append(f"| {i} | {x['merchant'].replace('|','/')} | {x['score']:.1f} | {x['visits']} | {x['mayor_visits']} | {x['vice_mayor_visits']} | {x['role_count']} | {x['months']} | {x['spend']:,} |")
    (REPORTS/"incheon-province-candidates.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"meal_rows":len(rows),"entities":len(out),"eligible":len(eligible),"top":eligible[:5]},ensure_ascii=False))


if __name__=="__main__":
    main()
