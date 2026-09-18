#!/usr/bin/env python3
from __future__ import annotations

import json, math, re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data"/"raw"/"central_executive_expense.json"
REPORTS=ROOT/"reports"
MEAL_WORDS=("간담","오찬","만찬","식사","회의","협의","논의","격려","소통","업무협의","현안","관계자","직원","방문","간담회")
EXCLUDE=("경조","축의","조의","화환","꽃","주유","주차","택시","교통","온라인","쿠팡","문구","물품","기념품","사무용","상품권","커피","카페","다과","간식","스타벅스","이디야","파리크라상","편의점","구내식당","정부청사","상호없음","해외출장")
SENIOR=("장관","차관","처장","차장","청장","부청장","실장","국장","본부장","총리","비서실장")
GENERIC_MERCHANTS={"상호없음","상호 없음","신화케이푸드","제이제이홈","제이티알"}
NON_DINING_MERCHANT_WORDS=(
    "구내식당","정부청사","국회본관식당","현대그린푸드","풀무원푸드앤컬처",
    "한화푸드테크","두레에프엔씨","푸드앤컬처","케이터링","급식",
    "은행","카드","캐피탈","보험","증권","렌터카","주유소","마트","편의점",
)

def t(v):return " ".join(str(v or "").split()).strip()
def canon_name(v):
    s=t(v);s=re.sub(r"^(?:주식회사|\(주\)|㈜)\s*","",s);return s.strip(" ,")
def canon_addr(v):return re.sub(r"\s+"," ",t(v).replace("서울특별시","서울").replace("서울시","서울")).strip(" ,")
def meal(r):
    p=t(r.get("purpose"));m=t(r.get("merchant"));c=p+" "+m
    if not m or canon_name(m) in GENERIC_MERCHANTS:return False
    if any(x in m for x in NON_DINING_MERCHANT_WORDS):return False
    if any(x in c for x in EXCLUDE):return False
    return any(x in p for x in MEAL_WORDS) or any(x in t(r.get("role")) for x in SENIOR)
def senior_weight(role):
    s=t(role)
    if "장관" in s and "차관" not in s:return 1.0
    if "차관" in s:return .9
    if any(x in s for x in ("처장","청장","본부장")):return .85
    if "실장" in s:return .75
    if "국장" in s:return .65
    return .5

ROLE_TIER_ORDER={
    "other":0,
    "director_general":1,
    "senior_official":2,
    "agency_head":3,
    "vice_minister":4,
    "minister":5,
    "deputy_prime_minister":6,
    "prime_minister":7,
}
ROLE_TIER_LABEL={
    "other":"기타 공개 직위",
    "director_general":"국장급",
    "senior_official":"실장급",
    "agency_head":"기관장·본부장급",
    "vice_minister":"차관급",
    "minister":"장관급",
    "deputy_prime_minister":"부총리급",
    "prime_minister":"국무총리급",
}

def role_tier(role):
    s=t(role)
    if "국무총리" in s or s=="총리":return "prime_minister"
    if "부총리" in s:return "deputy_prime_minister"
    if "장관" in s:return "minister"
    if "차관" in s:return "vice_minister"
    if any(x in s for x in ("처장","청장","본부장")):return "agency_head"
    if "실장" in s:return "senior_official"
    if "국장" in s:return "director_general"
    return "other"

def score(visits,roles,months,institutions,weight,senior_ratio,spend):
    return round(100*(
        .22*min(math.log1p(visits)/math.log1p(10),1)
        +.13*min(roles/5,1)
        +.15*min(months/6,1)
        +.15*min(institutions/4,1)
        +.20*weight
        +.10*min(max(senior_ratio,0),1)
        +.05*min(math.log1p(max(spend,0))/math.log1p(5_000_000),1)
    ),1)

def main():
    if not RAW.exists():
        print("central executive raw missing; no candidates built");return
    d=json.loads(RAW.read_text(encoding="utf-8"));rows=[
        r for r in d.get("rows",[])
        if meal(r) and re.fullmatch(r"20\d{2}-\d{2}-\d{2}",t(r.get("used_date")))
    ]
    if not rows:
        previous=REPORTS/"central-executive-candidates.json"
        if previous.exists():
            try:
                old=json.loads(previous.read_text(encoding="utf-8"))
            except (OSError,json.JSONDecodeError):
                old={}
            old_candidates=old.get("candidates") or []
            if old_candidates:
                print(json.dumps({
                    "meal_rows":0,
                    "preserved_last_good":len(old_candidates),
                    "reason":"central refresh produced zero meal rows",
                },ensure_ascii=False))
                return
    groups=defaultdict(list)
    for r in rows:groups[(canon_name(r.get("merchant")),canon_addr(r.get("address")))].append(r)
    out=[]
    for (name,address),items in groups.items():
        if not name:continue
        visits=len(items);roles=sorted({t(r.get("role")) or t(r.get("department")) for r in items if t(r.get("role")) or t(r.get("department"))})
        institutions=sorted({t(r.get("institution")) for r in items if t(r.get("institution"))})
        months=sorted({(t(r.get("used_date")))[:7] for r in items if re.match(r"20\d{2}-\d{2}",t(r.get("used_date")))})
        spend=sum(int(r.get("amount") or 0) for r in items if isinstance(r.get("amount"),(int,float)))
        weights=[senior_weight(r.get("role")) for r in items]
        weight=max(weights or [.5])
        senior_visits=sum(1 for w in weights if w>=.65)
        senior_ratio=senior_visits/visits if visits else 0
        tier_counts=Counter(role_tier(r.get("role")) for r in items)
        top_role_tier=max(tier_counts,key=lambda x:ROLE_TIER_ORDER.get(x,0)) if tier_counts else "other"
        top_official_visits=sum(tier_counts.get(x,0) for x in ("prime_minister","deputy_prime_minister","minister","vice_minister"))
        s=score(visits,len(roles),len(months),len(institutions),weight,senior_ratio,spend)
        rc=Counter(t(r.get("role")) or t(r.get("department")) or "직위 미상" for r in items);pc=Counter(t(r.get("purpose")) for r in items if t(r.get("purpose")))
        dates=sorted(t(r.get("used_date")) for r in items if re.fullmatch(r"20\d{2}-\d{2}-\d{2}",t(r.get("used_date"))))
        out.append({"merchant":name,"address":address,"score":s,"visits":visits,"senior_visits":senior_visits,"senior_ratio":round(senior_ratio,3),"role_count":len(roles),"institution_count":len(institutions),"months":len(months),"spend":spend,"senior_weight":weight,"top_role_tier":top_role_tier,"top_role_label":ROLE_TIER_LABEL.get(top_role_tier,top_role_tier),"top_official_visits":top_official_visits,"prime_minister_visits":tier_counts.get("prime_minister",0),"deputy_prime_minister_visits":tier_counts.get("deputy_prime_minister",0),"minister_visits":tier_counts.get("minister",0),"vice_minister_visits":tier_counts.get("vice_minister",0),"role_tier_stats":[{"tier":k,"label":ROLE_TIER_LABEL.get(k,k),"visits":v} for k,v in sorted(tier_counts.items(),key=lambda kv:ROLE_TIER_ORDER.get(kv[0],0),reverse=True)],"institutions":institutions,"role_stats":[{"role":k,"visits":v} for k,v in rc.most_common(10)],"purpose_stats":[{"text":k,"count":v} for k,v in pc.most_common(6)],"date_min":dates[0] if dates else "","date_max":dates[-1] if dates else "","recent":[{"date":t(r.get("used_date")),"time":t(r.get("used_time")),"institution":t(r.get("institution")),"role":t(r.get("role")) or t(r.get("department")),"amount":int(r.get("amount") or 0),"people":int(r.get("people") or 0),"purpose":t(r.get("purpose")),"source":t(r.get("source_url"))} for r in sorted(items,key=lambda x:(t(x.get("used_date")),t(x.get("used_time"))),reverse=True)[:8]]})
    eligible=[x for x in out if x["visits"]>=2 and x["months"]>=1 and x["score"]>=45 and (x["senior_weight"]>=.65 or x["institution_count"]>=2)]
    eligible.sort(key=lambda x:(x["score"],x["institution_count"],x["visits"],x["spend"]),reverse=True)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS/"central-executive-candidates.json").write_text(json.dumps({"generated_at":datetime.now().isoformat(timespec="seconds"),"source":"central_executive","cohort":"central_executive","entity_count":len(out),"eligible_count":len(eligible),"candidates":eligible[:200]},ensure_ascii=False,indent=2),encoding="utf-8")
    md=["# Central executive dining candidates","",f"- Meal-like rows: **{len(rows)}**",f"- Entities: **{len(out)}**",f"- Eligible: **{len(eligible)}**","","> Ranking prioritizes documented minister/vice-minister/senior-executive use; generic departmental rows alone do not qualify unless the restaurant is independently repeated across institutions.","","| # | Merchant | Score | Visits | Senior visits | Institutions | Roles | Months | Spend |","|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    for i,x in enumerate(eligible[:100],1):md.append(f"| {i} | {x['merchant'].replace('|','/')} | {x['score']:.1f} | {x['visits']} | {x['senior_visits']} | {x['institution_count']} | {x['role_count']} | {x['months']} | {x['spend']:,} |")
    (REPORTS/"central-executive-candidates.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"meal_rows":len(rows),"entities":len(out),"eligible":len(eligible),"published_stage":min(len(eligible),200)},ensure_ascii=False))

if __name__=="__main__":main()
