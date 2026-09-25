#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import math
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW_DIR=ROOT/"data"/"raw"
REPORTS=ROOT/"reports"
PAGE="https://pages.newstapa.org/2023/07_prosecution/expense.html"
ORIGINALS="https://drive.google.com/drive/folders/1lhDRPNe-cuDM9Zzo0hjbJE8OBCTVOTps"
UA="ExecutiveDiningSeoul/2.1 (+https://github.com/mrunderdog/executive-dining-seoul)"

ACTORS={
    "k":{"person":"김수남","role":"검찰총장"},
    "m":{"person":"문무일","role":"검찰총장"},
    "b":{"person":"배성범","role":"서울중앙지검장"},
    "y":{"person":"윤석열","role":"서울중앙지검장·검찰총장"},
    "e":{"person":"이영렬","role":"서울중앙지검장"},
}
INTERNAL_WORDS=("구내식당","매점")
NON_RESTAURANT_MARKERS=("주소 불일치",)
INSTITUTION_ONLY_PATTERNS=(
    r"(?:고등|지방)?검찰청(?:\s+\S+지청)?$",
    r"(?:지검|지청)$",
)
INSTITUTIONAL_DINING_NAMES={"국회 식당"}


def fetch_text(url:str)->str:
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,*/*;q=0.8"})
    with urllib.request.urlopen(req,timeout=30) as r:
        raw=r.read()
        enc=r.headers.get_content_charset() or "utf-8"
    return raw.decode(enc,errors="replace")


def find_expense_chunk(page_html:str)->str:
    matches=re.findall(r'''static/chunks/app/expense/page-[A-Za-z0-9_-]+\.js''',page_html)
    if not matches:
        raise RuntimeError("expense page chunk not found")
    rel=matches[-1]
    return urllib.parse.urljoin(PAGE,"./_next/"+rel)


def extract_feature_collection(js:str)->dict:
    for m in re.finditer(r'''JSON\.parse\(('(?:\\.|[^'\\])*')\)''',js,re.S):
        literal=m.group(1)
        try:
            decoded=ast.literal_eval(literal)
            obj=json.loads(decoded)
        except Exception:
            continue
        if not isinstance(obj,dict) or obj.get("type")!="FeatureCollection":
            continue
        features=obj.get("features")
        if not isinstance(features,list) or not features:
            continue
        sample=features[0] if isinstance(features[0],dict) else {}
        props=sample.get("properties") if isinstance(sample,dict) else {}
        if isinstance(props,dict) and {"name","count","price"}.issubset(props):
            return obj
    raise RuntimeError("restaurant FeatureCollection not found in expense page chunk")


def score(visits:int,actors:int,spend:int)->float:
    return round(100*(
        .55*min(math.log1p(max(visits,0))/math.log1p(25),1)
        +.25*min(max(actors,0)/3,1)
        +.20*min(math.log1p(max(spend,0))/math.log1p(15_000_000),1)
    ),1)


def normalize_feature(feature:dict)->dict|None:
    if not isinstance(feature,dict):
        return None
    props=feature.get("properties") or {}
    geom=feature.get("geometry") or {}
    coords=geom.get("coordinates") or []
    name=" ".join(str(props.get("name") or "").split()).strip()
    if not name:
        return None
    actor_stats=[]
    for key,meta in ACTORS.items():
        value=props.get(key)
        visits=int(value or 0) if isinstance(value,(int,float)) else 0
        if visits:
            actor_stats.append({**meta,"visits":visits})
    visits=int(props.get("count") or 0)
    spend=int(props.get("price") or 0)
    avg=int(props.get("per1") or 0)
    address=" ".join(str(props.get("주소") or "").split()).strip()
    lon=coords[0] if len(coords)>=2 and isinstance(coords[0],(int,float)) else None
    lat=coords[1] if len(coords)>=2 and isinstance(coords[1],(int,float)) else None
    return {
        "merchant":name,
        "address":address,
        "lat":lat,
        "lon":lon,
        "visits":visits,
        "spend":spend,
        "avg_per_visit":avg,
        "actor_count":len(actor_stats),
        "actor_stats":actor_stats,
        "source_tag":str(props.get("tag") or ""),
        "source_no":props.get("no"),
        "score":score(visits,len(actor_stats),spend),
        "internal_venue":any(word in name for word in INTERNAL_WORDS),
        "non_restaurant_entity":(
            any(marker in name for marker in NON_RESTAURANT_MARKERS)
            or any(re.search(pattern,name) for pattern in INSTITUTION_ONLY_PATTERNS)
            or name in INSTITUTIONAL_DINING_NAMES
        ),
        "period":"2017-01~2019-09",
        "historical":True,
        "source_type":"court_ordered_disclosure_secondary_archive",
        "source_url":PAGE,
        "original_docs_url":ORIGINALS,
    }


def main():
    html=fetch_text(PAGE)
    chunk_url=find_expense_chunk(html)
    js=fetch_text(chunk_url)
    geo=extract_feature_collection(js)
    rows=[r for f in geo.get("features",[]) if (r:=normalize_feature(f))]
    rows.sort(key=lambda x:(x["visits"],x["spend"]),reverse=True)

    RAW_DIR.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    generated=datetime.now().isoformat(timespec="seconds")
    raw={
        "schema_version":1,
        "generated_at":generated,
        "source":"newstapa_prosecution_expense_map",
        "source_page":PAGE,
        "source_chunk":chunk_url,
        "original_docs_url":ORIGINALS,
        "period":"2017-01~2019-09",
        "row_count":len(rows),
        "rows":rows,
    }
    (RAW_DIR/"prosecution_archive_restaurants.json").write_text(
        json.dumps(raw,ensure_ascii=False,indent=2),encoding="utf-8"
    )

    published=[
        r for r in rows
        if not r["internal_venue"]
        and not r["non_restaurant_entity"]
        and r["visits"]>0
    ]
    report={
        "generated_at":generated,
        "source":"prosecution_archive_2017_2019",
        "cohort":"justice_leadership",
        "historical":True,
        "period":"2017-01~2019-09",
        "entity_count":len(rows),
        "eligible_count":len(published),
        "candidates":published,
    }
    (REPORTS/"prosecution-archive-candidates.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    md=[
        "# Prosecution expense restaurant archive — 2017-01~2019-09","",
        f"- GeoJSON entities: **{len(rows)}**",
        f"- External venues: **{len(published)}**",
        f"- Embedded page chunk: {chunk_url}","",
        "> Historical signal reconstructed and published by Newstapa and civic groups from court-ordered prosecution expense receipts. It is kept separate from current routine prosecution disclosures.","",
        "| # | Merchant | Visits | Spend | Avg/visit | Senior officials | Address |",
        "|---:|---|---:|---:|---:|---:|---|",
    ]
    for i,r in enumerate(published,1):
        md.append(
            f"| {i} | {r['merchant'].replace('|','/')} | {r['visits']} | {r['spend']:,} | "
            f"{r['avg_per_visit']:,} | {r['actor_count']} | {r['address'].replace('|','/')} |"
        )
    (REPORTS/"prosecution-archive-candidates.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({
        "entities":len(rows),"external":len(published),
        "top":[{"merchant":r["merchant"],"visits":r["visits"],"spend":r["spend"]} for r in published[:8]]
    },ensure_ascii=False))


if __name__=="__main__":
    main()
