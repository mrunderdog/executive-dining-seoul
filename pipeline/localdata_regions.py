"""LOCALDATA jurisdiction routing for publicly disclosed restaurant addresses.

Community-sourced org codes are discovery hints. A downloaded CSV's identity
and quality must be checked before a jurisdiction can become VERIFIED.
"""
from __future__ import annotations
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"sources/localdata_orgcodes.json"
PROVINCE_ALIASES={
    "서울":["서울특별시","서울시","서울"],
    "부산":["부산광역시","부산시","부산"],
    "대구":["대구광역시","대구시","대구"],
    "인천":["인천광역시","인천시","인천"],
    "광주":["광주광역시","광주시","광주"],
    "대전":["대전광역시","대전시","대전"],
    "울산":["울산광역시","울산시","울산"],
    "세종특별자치시":["세종특별자치시","세종시","세종"],
    "경기":["경기도","경기"],
    "강원":["강원특별자치도","강원도","강원"],
    "충북":["충청북도","충북"],
    "충남":["충청남도","충남"],
    "전북":["전북특별자치도","전라북도","전북"],
    "전남":["전라남도","전남"],
    "경북":["경상북도","경북"],
    "경남":["경상남도","경남"],
    "제주":["제주특별자치도","제주도","제주"]
}
ROAD_PATTERN=re.compile(r"(?<![가-힣0-9])([가-힣0-9]+(?:로|길))\s*(\d+(?:-\d+)?)(?!\d)")

@lru_cache(maxsize=1)
def registry_codes():
    content=json.loads(REGISTRY.read_text(encoding="utf-8"))
    return content["codes"]

def route_localdata(address, codes=None):
    """Route only an explicit, unambiguous administrative name.

    Permits space-omitted official prefixes (서울영등포구...) and a province-less
    UNIQUE district/county label (서초구 ...). Never use agency origin as a
    location, never infer locality from road name or merchant name.
    """
    codes = codes if codes is not None else registry_codes()
    compact = re.sub(r"\\s+", "", str(address or ""))
    if not compact:
        return None

    # Explicit province takes precedence over all locality-only interpretations.
    for label, aliases in PROVINCE_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            if not compact.startswith(alias):
                continue
            rest = compact[len(alias):]
            if not rest:
                return None
            if label == "세종특별자치시":
                name = "세종특별자치시 본청"
                return (name, codes[name]) if name in codes else None
            matches = [(name, code) for name, code in codes.items()
                       if name.startswith(label) and not name.endswith("본청")
                       and name[len(label):]
                       and rest.startswith(name[len(label):])]
            if matches:
                return max(matches, key=lambda x: len(x[0]))
            # Recognized province with no district must NOT be guessed.
            return None

    # Only county/district prefixes unique across ALL national registry rows.
    # "중구" and "강서구" are duplicated across cities and stay unresolved.
    localities = {}
    for name, code in codes.items():
        if name.endswith("본청"):
            continue
        province = next((p for p in PROVINCE_ALIASES if name.startswith(p)), None)
        if not province:
            continue
        suffix = name[len(province):]
        if suffix.endswith(("구", "군")) and suffix:
            localities.setdefault(suffix, []).append((name, code))
    choices = [(suffix, rows[0]) for suffix, rows in localities.items()
               if len(rows) == 1 and compact.startswith(suffix) and len(compact) > len(suffix)]
    if not choices:
        return None
    return max(choices, key=lambda x: len(x[0]))[1]

def building_key(address,codes=None):
    found=route_localdata(address,codes)
    if not found:return ""
    match=ROAD_PATTERN.search(str(address or ""))
    if not match:return ""
    return found[1]+"|"+match[1].lower()+match[2]

def summarize_coverage(records,codes=None):
    codes=codes if codes is not None else registry_codes()
    by={}
    out=[]
    missing_reasons={}
    unrouted_origin_counts={}
    unrouted_origin_reasons={}
    for rec in records:
        addr=str(rec.get("address") or "").strip()
        routed=route_localdata(addr,codes)
        if not routed:
            reason="MISSING_ADDRESS" if not addr else "UNROUTABLE_JURISDICTION"
            missing_reasons[reason]=missing_reasons.get(reason,0)+1
            origins=sorted(set(str(x) for x in (rec.get("origins") or [rec.get("origin")]) if x))
            for origin in origins:
                unrouted_origin_counts[origin]=unrouted_origin_counts.get(origin,0)+1
                per=unrouted_origin_reasons.setdefault(origin,{"MISSING_ADDRESS":0,"UNROUTABLE_JURISDICTION":0})
                per[reason]+=1
            e=rec.get("evidence") or {}
            out.append({"entity_id":str(rec.get("entity_id") or ""), "name":str(rec.get("name") or ""),
                        "address":addr[:150],"reason":reason,"origins":origins,
                        "reported_usage_events":int(e.get("visits") or 0),
                        "disclosed_spending_events":int(e.get("spending_events") or 0)})
            continue
        name,code=routed
        stats=by.setdefault(name,{"region":name,"orgCode":code,"venues":0,"with_road_building":0,
                                  "missing_road_building":0,"institution_origins":{}})
        stats["venues"]+=1
        if building_key(addr,codes):stats["with_road_building"]+=1
        else:stats["missing_road_building"]+=1
        origins=rec.get("origins") or ([rec.get("origin")] if rec.get("origin") else [])
        for origin in set(str(x) for x in origins if x):
            stats["institution_origins"][origin]=stats["institution_origins"].get(origin,0)+1
    ranked=[]
    for row in by.values():
        row["institution_origin_count"]=len(row["institution_origins"])
        row["top_origins"]=sorted(row["institution_origins"].items(),key=lambda x:(-x[1],x[0]))[:7]
        del row["institution_origins"]
        ranked.append(row)
    ranked.sort(key=lambda r:(-r["with_road_building"],-r["venues"],r["region"]))
    return {"total_published_venues":len(records),"routed_venues":sum(x["venues"] for x in ranked),
            "road_building_verifiable":sum(x["with_road_building"] for x in ranked),
            "unrouted_venues":len(out),"unrouted_reason_counts":missing_reasons,
            "unrouted_top_origins":sorted(unrouted_origin_counts.items(),key=lambda x:(-x[1],x[0]))[:15],
            "unrouted_samples":out[:20],
            "unrouted_by_origin":[{"origin":origin,**counts,"affected_venue_attributions":sum(counts.values())}
                                  for origin,counts in sorted(unrouted_origin_reasons.items(),
                                      key=lambda kv:(-sum(kv[1].values()),kv[0]))],
            "unrouted_review_queue":sorted(out,key=lambda x:(
                -(x["reported_usage_events"]+x["disclosed_spending_events"]),
                x["name"],x["entity_id"])),
            "regions":ranked,"source_registry":"sources/localdata_orgcodes.json",
            "routing_policy":"Exact province/city/district and road-building only; no guesses for missing addresses."}

if __name__=="__main__":
    from data_io import load_payload
    from published_sources import merge_published_sources
    from extra_published import merge_extra_published
    from global_entities import merge_global_entities
    payload=merge_global_entities(merge_extra_published(merge_published_sources(load_payload())))
    report=summarize_coverage(payload.get("records") or [])
    backlog=report.pop("unrouted_review_queue")
    target=ROOT/"reports/localdata-regional-coverage.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    backlog_path=ROOT/"reports/localdata-address-remediation-queue.json"
    backlog_path.write_text(json.dumps({"generated_from":"published records with no proven locality or road address",
        "total_unrouted":len(backlog),
        "policy":"Venue names/usage counts never justify guessing a geographic location. Verify using a public source before assigning one.",
        "records":backlog},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("total_published_venues","routed_venues","road_building_verifiable","unrouted_venues")},ensure_ascii=False))
    print("TOP_REGIONS="+json.dumps(report["regions"][:15],ensure_ascii=False))
