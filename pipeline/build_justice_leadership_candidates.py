#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data"/"raw"/"justice_leadership_expense.json"
REPORTS=ROOT/"reports"

MEAL_WORDS=("간담","오찬","만찬","식사","식비","업무협의","현안","협의","논의","격려","소통","관계자","직원")
EXCLUDE_WORDS=("경조","축의","조의","화환","꽃","주유","주차","택시","교통","온라인","쿠팡","문구","물품","기념품","사무용","상품권","커피","카페","다과","간식","편의점","마트")
NON_DINING=("구내식당","정부청사","은행","카드","보험","증권","렌터카","주유소")
GENERIC={"상호없음","상호 없음","미상","확인불가","확인 불가","-"}


def t(v): return " ".join(str(v or "").split()).strip()


def canon_name(v):
    s=t(v)
    s=re.sub(r"^(?:주식회사|\(주\)|㈜)\s*","",s)
    return s.strip(" ,")


def canon_addr(v):
    return re.sub(r"\s+"," ",t(v).replace("서울특별시","서울").replace("서울시","서울")).strip(" ,")


def role_weight(role:str)->float:
    s=t(role)
    if "대법원장" in s or "헌법재판소장" in s or "검찰총장" in s: return 1.0
    if "고검장" in s or "법무부 장관" in s or "고위공직자범죄수사처장" in s: return .95
    if "법원행정처장" in s or "고등법원장" in s or "지방법원장" in s or "특허법원장" in s or "행정법원장" in s or "회생법원장" in s: return .9
    if "검사장" in s or "지청장" in s or "법제처장" in s: return .88
    if "헌법재판소사무처장" in s or "법무부 차관" in s or "법제처차장" in s: return .85
    if any(x in s for x in ("법무실장","검찰국장","국제법무국장","감찰관","본부장","기획조정실장")): return .78
    if any(x in s for x in ("국장","정책관","조정관")): return .65
    return .5


def role_tier(role:str)->str:
    w=role_weight(role)
    if w>=.98:return "constitutional_judicial_prosecution_head"
    if w>=.93:return "cabinet_or_investigative_head"
    if w>=.88:return "court_or_prosecution_agency_head"
    if w>=.84:return "deputy_head"
    if w>=.75:return "senior_legal_official"
    if w>=.6:return "director_level"
    return "other"


def plausible_merchant(v)->bool:
    s=canon_name(v)
    if not s or s in GENERIC:return False
    if re.fullmatch(r"[\d,.:\-\s]+",s):return False
    compact=re.sub(r"\s+","",s)
    if len(compact)>45 and any(x in compact for x in ("간담","협의","논의","업무추진비","집행내역")):return False
    if any(x in s for x in NON_DINING):return False
    return True


def meal_like(r)->bool:
    m=canon_name(r.get("merchant")); p=t(r.get("purpose")); c=m+" "+p
    if not plausible_merchant(m):return False
    if any(x in c for x in EXCLUDE_WORDS):return False
    return any(x in p for x in MEAL_WORDS) or role_weight(r.get("payer_role") or r.get("role"))>=.85


def score(visits,months,roles,weight,high_ratio,spend):
    return round(100*(
        .25*min(math.log1p(visits)/math.log1p(8),1)
        +.15*min(months/6,1)
        +.10*min(roles/5,1)
        +.25*weight
        +.15*min(high_ratio,1)
        +.10*min(math.log1p(max(spend,0))/math.log1p(3_000_000),1)
    ),1)


def main():
    if not RAW.exists():
        print("justice leadership raw missing; no candidates built"); return
    d=json.loads(RAW.read_text(encoding="utf-8"))
    rows=[r for r in d.get("rows",[])
          if re.fullmatch(r"20\d{2}-\d{2}-\d{2}",t(r.get("used_date"))) and meal_like(r)]
    groups=defaultdict(list)
    for r in rows:
        groups[(canon_name(r.get("merchant")),canon_addr(r.get("address")))].append(r)
    out=[]
    for (name,address),items in groups.items():
        if not name:continue
        visits=len(items)
        roles=[t(r.get("payer_role") or r.get("role")) for r in items]
        role_set=sorted({x for x in roles if x})
        weights=[role_weight(x) for x in roles]
        top_weight=max(weights or [.5])
        high=sum(w>=.65 for w in weights)
        high_ratio=high/visits if visits else 0
        months=sorted({t(r.get("used_date"))[:7] for r in items})
        spend=sum(int(r.get("amount") or 0) for r in items if isinstance(r.get("amount"),(int,float)))
        institutions=sorted({t(r.get("institution")) for r in items if t(r.get("institution"))})
        domains=sorted({t(r.get("justice_domain")) for r in items if t(r.get("justice_domain"))})
        rc=Counter(roles); pc=Counter(t(r.get("purpose")) for r in items if t(r.get("purpose")))
        dates=sorted(t(r.get("used_date")) for r in items)
        s=score(visits,len(months),len(role_set),top_weight,high_ratio,spend)
        top_role=max(role_set,key=role_weight) if role_set else ""
        out.append({
            "merchant":name,"address":address,"score":s,"visits":visits,"months":len(months),
            "spend":spend,"role_count":len(role_set),"institution_count":len(institutions),
            "institutions":institutions,"domains":domains,"top_role":top_role,
            "top_role_tier":role_tier(top_role),"top_role_weight":top_weight,
            "high_official_visits":high,"high_official_ratio":round(high_ratio,3),
            "role_stats":[{"role":k,"visits":v} for k,v in rc.most_common(12) if k],
            "purpose_stats":[{"text":k,"count":v} for k,v in pc.most_common(8)],
            "date_min":dates[0] if dates else "","date_max":dates[-1] if dates else "",
            "recent":[{
                "date":t(r.get("used_date")),"time":t(r.get("used_time")),
                "institution":t(r.get("institution")),"role":t(r.get("payer_role") or r.get("role")),
                "amount":int(r.get("amount") or 0),"people":int(r.get("people") or 0),
                "purpose":t(r.get("purpose")),"source":t(r.get("source_url")),
                "source_type":t(r.get("source_type"))
            } for r in sorted(items,key=lambda x:(t(x.get("used_date")),t(x.get("used_time"))),reverse=True)[:10]]
        })
    eligible=[x for x in out if x["high_official_visits"]>=1
              and (x["visits"]>=2 or x["top_role_weight"]>=.85)
              and x["score"]>=30]
    eligible.sort(key=lambda x:(x["score"],x["top_role_weight"],x["visits"],x["spend"]),reverse=True)
    REPORTS.mkdir(exist_ok=True)
    payload={"generated_at":datetime.now().isoformat(timespec="seconds"),"source":"justice_leadership",
             "cohort":"justice_leadership","meal_rows":len(rows),"entity_count":len(out),
             "eligible_count":len(eligible),"candidates":eligible[:200]}
    (REPORTS/"justice-leadership-candidates.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    md=["# Justice leadership dining candidates","",f"- Meal-like rows: **{len(rows)}**",
        f"- Entities: **{len(out)}**",f"- Eligible: **{len(eligible)}**","",
        "> 법조·법률행정 고위직의 공개 업무추진비에 나타난 사용처 후보입니다. 점수는 식당 품질 평가가 아니라 반복·직위·기간 신호입니다.","",
        "| # | Merchant | Score | Visits | Top role | Institutions | Months | Spend |",
        "|---:|---|---:|---:|---|---:|---:|---:|"]
    for i,x in enumerate(eligible[:100],1):
        md.append(f"| {i} | {x['merchant'].replace('|','/')} | {x['score']:.1f} | {x['visits']} | {x['top_role']} | {x['institution_count']} | {x['months']} | {x['spend']:,} |")
    (REPORTS/"justice-leadership-candidates.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"meal_rows":len(rows),"entities":len(out),"eligible":len(eligible)},ensure_ascii=False))


if __name__=="__main__": main()
