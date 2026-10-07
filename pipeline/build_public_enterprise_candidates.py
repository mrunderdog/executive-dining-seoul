#!/usr/bin/env python3
from __future__ import annotations
import json, math, re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data"/"raw"/"public_enterprise_expense.json"
REPORTS=ROOT/"reports"
MEAL_WORDS=("간담","오찬","만찬","식사","회의","협의","논의","격려","소통","업무협의","현안","관계자","직원","방문","간담회")
EXCLUDE=("경조","축의","조의","화환","화분","화훼","플라워","꽃","주유","주차","택시","교통","온라인","쿠팡","문구","물품","기념품","사무용","상품권","커피","카페","다과","간식","편의점","마트","구내식당","구내복지센터","구내복지")
GENERIC={"상호없음","상호 없음","미상","확인불가","확인 불가","-","마곡점"}

def t(v):return " ".join(str(v or "").split()).strip()
def canon(v):
    s=t(v);s=re.sub(r"^(?:주식회사|\(주\)|㈜)\s*","",s)
    s=re.sub(r"\s*\(\s*[☎☏]?\s*\d{2,3}-\d{3,4}-\d{4}\s*\)\s*$","",s)
    s=re.sub(r"\s*\(\s*\d{3}-\d{2}-\d{5}\s*\)\s*$","",s)
    return s.strip(" ,")

def phone_from(v):
    m=re.search(r"(\d{2,3}-\d{3,4}-\d{4})",t(v))
    return m.group(1) if m else ""
def addr(v):return re.sub(r"\s+"," ",t(v).replace("서울특별시","서울").replace("서울시","서울")).strip(" ,")
def meal(r):
    m=canon(r.get("merchant"));p=t(r.get("purpose"));c=m+" "+p
    if r.get("source_key")=="kwater" and re.search(r"펠리쓰\s*팩토리아",m):
        # The 28,000-won K-water transaction is at a verified coffee roastery/cafe,
        # not an executive dining venue.
        return False
    if r.get("source_key")=="kogas":
        if re.search(r"위문|사기\s*진작",t(r.get("source_category"))):
            return False
        # KOGAS institution-head sheets also contain bulk welfare/refreshment
        # purchases whose category can be blank after merged-cell extraction.
        # These verified cafe/fruit merchants are not executive dining venues.
        if re.search(r"이루팜|빅핸즈",m):
            return False
    if not m or m in GENERIC or re.fullmatch(r"[\d,.:\-\s]+",m):return False
    if any(x in c for x in EXCLUDE):return False
    return any(x in p for x in MEAL_WORDS) or t(r.get("role")) in {"기관장","사장","사장직무대행"}
def score(visits,months,spend):
    return round(100*(.45*min(math.log1p(visits)/math.log1p(8),1)+.25*min(months/6,1)+.20+.10*min(math.log1p(max(spend,0))/math.log1p(3_000_000),1)),1)

def balanced_candidates(eligible,incumbents=None,publish_window=180,min_per_institution=10,max_candidates=250):
    """Keep verified incumbents per institution, then fill the publish window by current global score."""
    def key(candidate):
        return (t(candidate.get("merchant")),t(candidate.get("address")))
    eligible_by_key={key(candidate):candidate for candidate in eligible}
    institutions=sorted({inst for candidate in eligible for inst in (candidate.get("institutions") or []) if t(inst)})
    quota=min(min_per_institution,max(1,publish_window//max(1,len(institutions))))
    reserved=set()
    incumbents=incumbents or []
    for inst in institutions:
        count=0
        for old in incumbents:
            if inst not in (old.get("institutions") or []):continue
            k=key(old)
            if k not in eligible_by_key or k in reserved:continue
            reserved.add(k);count+=1
            if count>=quota:break
        if count<quota:
            for candidate in eligible:
                if inst not in (candidate.get("institutions") or []):continue
                k=key(candidate)
                if k in reserved:continue
                reserved.add(k);count+=1
                if count>=quota:break
    selected=set(reserved)
    for candidate in eligible:
        if len(selected)>=publish_window:break
        selected.add(key(candidate))
    front=[candidate for candidate in eligible if key(candidate) in selected]
    ranked=list(front)
    seen=set(selected)
    for candidate in eligible:
        if len(ranked)>=max_candidates:break
        k=key(candidate)
        if k in seen:continue
        ranked.append(candidate);seen.add(k)
    return ranked[:max_candidates]

def main():
    if not RAW.exists():print("public-enterprise raw missing; no candidates built");return
    incumbent_candidates=[]
    incumbent_path=REPORTS/"public-enterprise-candidates.json"
    if incumbent_path.exists():
        try:incumbent_candidates=(json.loads(incumbent_path.read_text(encoding="utf-8")).get("candidates") or [])
        except Exception:incumbent_candidates=[]
    d=json.loads(RAW.read_text(encoding="utf-8"))
    rows=[r for r in d.get("rows",[]) if r.get("cohort")=="public_enterprise_leadership" and meal(r) and re.fullmatch(r"20\d{2}-\d{2}-\d{2}",t(r.get("used_date")))]
    if not rows:
        old=REPORTS/"public-enterprise-candidates.json"
        if old.exists():
            try:o=json.loads(old.read_text(encoding="utf-8"))
            except Exception:o={}
            if o.get("candidates"):
                print(json.dumps({"meal_rows":0,"preserved_last_good":len(o["candidates"])},ensure_ascii=False));return
    groups=defaultdict(list)
    for r in rows:groups[(canon(r.get("merchant")),addr(r.get("address")))].append(r)
    out=[]
    for (name,address),items in groups.items():
        visits=len(items);months=sorted({t(x.get("used_date"))[:7] for x in items});spend=sum(int(x.get("amount") or 0) for x in items if isinstance(x.get("amount"),(int,float)))
        inst=sorted({t(x.get("institution")) for x in items if t(x.get("institution"))})
        dates=sorted(t(x.get("used_date")) for x in items)
        pc=Counter(t(x.get("purpose")) for x in items if t(x.get("purpose")))
        rc=Counter(t(x.get("role")) for x in items if t(x.get("role")))
        phones=[phone_from(x.get("merchant")) for x in items if phone_from(x.get("merchant"))]
        s=score(visits,len(months),spend)
        out.append({"merchant":name,"address":address,"phone":phones[0] if phones else "","score":s,"visits":visits,"months":len(months),"spend":spend,"institution_count":len(inst),"institutions":inst,"date_min":dates[0] if dates else "","date_max":dates[-1] if dates else "","purpose_stats":[{"text":k,"count":v} for k,v in pc.most_common(8)],"role_stats":[{"role":k,"visits":v} for k,v in rc.most_common()],"recent":[{"date":t(x.get("used_date")),"time":t(x.get("used_time")),"institution":t(x.get("institution")),"role":t(x.get("role")),"amount":int(x.get("amount") or 0),"people":int(x.get("people") or 0),"purpose":t(x.get("purpose")),"source":t(x.get("source_url"))} for x in sorted(items,key=lambda z:(t(z.get("used_date")),t(z.get("used_time"))),reverse=True)[:10]]})
    eligible=[x for x in out if x["visits"]>=1 and x["score"]>=25]
    eligible.sort(key=lambda x:(x["score"],x["visits"],x["spend"]),reverse=True)
    ranked=balanced_candidates(eligible,incumbent_candidates)
    REPORTS.mkdir(exist_ok=True)
    payload={"generated_at":datetime.now().isoformat(timespec="seconds"),"source":"public_enterprise_leadership","cohort":"public_enterprise_leadership","meal_rows":len(rows),"entity_count":len(out),"eligible_count":len(eligible),"candidates":ranked}
    (REPORTS/"public-enterprise-candidates.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    md=["# Public-enterprise leadership dining candidates","",f"- Meal-like rows: **{len(rows)}**",f"- Entities: **{len(out)}**",f"- Eligible: **{len(eligible)}**","","> 공기업·공공기관 기관장·임원 공개 업무추진비의 식사성 사용처입니다. 점수는 식당 품질 평가가 아닙니다.","","| # | Merchant | Score | Visits | Institutions | Months | Spend |","|---:|---|---:|---:|---:|---:|---:|"]
    for i,x in enumerate(ranked[:120],1):md.append(f"| {i} | {x['merchant'].replace('|','/')} | {x['score']:.1f} | {x['visits']} | {x['institution_count']} | {x['months']} | {x['spend']:,} |")
    (REPORTS/"public-enterprise-candidates.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"meal_rows":len(rows),"entities":len(out),"eligible":len(eligible),"ranked":len(ranked)},ensure_ascii=False))

if __name__=="__main__":main()
