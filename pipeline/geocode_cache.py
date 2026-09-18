#!/usr/bin/env python3
"""Persistent build-time geocoding for the public restaurant map.

Published capital-area rows without a source address are resolved only inside their
origin jurisdiction. Central-government and National Assembly supplements are also
included in the same published-record merge used by the site build.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from data_io import load_payload
from published_sources import merge_published_sources
from extra_published import merge_extra_published

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "geocode_cache.json"
USER_AGENT = "ExecutiveDiningSeoul/1.5 (+https://github.com/mrunderdog/executive-dining-seoul)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
ARCGIS = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
GEOCODER_VERSION = 4
POLICY_VERSION = 3

JURISDICTION_BOUNDS = {
    "고양시": (126.65, 37.48, 126.98, 37.80),
    "고양특례시": (126.65, 37.48, 126.98, 37.80),
    "수원시": (126.90, 37.20, 127.12, 37.36),
    "수원특례시": (126.90, 37.20, 127.12, 37.36),
    "부평구": (126.65, 37.47, 126.78, 37.57),
    "김포시": (126.50, 37.55, 126.85, 37.82),
    "안산시": (126.45, 37.18, 126.95, 37.42),
    "파주시": (126.65, 37.65, 127.05, 38.05),
    "안성시": (127.15, 36.90, 127.55, 37.20),
    "이천시": (127.30, 37.00, 127.70, 37.40),
    "오산시": (126.98, 37.10, 127.12, 37.22),
    "포천시": (127.00, 37.65, 127.50, 38.20),
    "양평군": (127.30, 37.30, 127.95, 37.75),
    "경기도": (126.30, 36.85, 127.85, 38.30),
    "경기도청": (126.30, 36.85, 127.85, 38.30),
    "인천광역시": (126.20, 37.20, 126.85, 37.85),
    "인천시청": (126.20, 37.20, 126.85, 37.85),
}


def clean(v) -> str:
    return " ".join(str(v or "").replace("\n", " ").split()).strip()


def norm_name(v) -> str:
    s = re.sub(r"\([^)]*\)", "", clean(v)).lower()
    s = re.sub(r"(?:주식회사|\(주\)|㈜|유한회사)", "", s)
    return re.sub(r"[^0-9a-z가-힣]", "", s)


def clean_address(v) -> str:
    s = clean(v)
    if not s:
        return ""
    s = s.replace("@", " ").replace("[", " ").replace("]", " ")
    s = re.sub(r"\([^)]*\)", " ", s).split(",", 1)[0]
    s = re.sub(r"(?<=\d)-0(?=\s|$)", "", s)
    s = re.sub(r"\b(?:지하\s*)?\d+층\b.*$", "", s)
    s = re.sub(r"\b\d+호\b.*$", "", s)
    return " ".join(s.split()).strip(" ,")


def fingerprint(r: dict) -> str:
    b = r.get("business") or {}
    raw = "|".join((clean(r.get("name")), clean(b.get("display")), clean(r.get("address")), clean(r.get("search_query"))))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def load_cache() -> dict:
    if not CACHE.exists():
        return {"meta": {}, "records": {}}
    try:
        obj = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"meta": {}, "records": {}}
    return obj if "records" in obj else {"meta": {}, "records": obj if isinstance(obj, dict) else {}}


def save_cache(cache: dict) -> None:
    recs = cache.get("records", {})
    cache["meta"] = {
        "providers": ["ArcGIS World Geocoding Service", "OpenStreetMap Nominatim"],
        "geocoder_version": GEOCODER_VERSION,
        "policy_version": POLICY_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "record_count": len(recs),
        "success_count": sum(isinstance(v, dict) and isinstance(v.get("lat"), (int, float)) for v in recs.values()),
        "failed_count": sum(isinstance(v, dict) and bool(v.get("failed")) for v in recs.values()),
    }
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def source_bounds(r: dict):
    if not r.get("published_source") or clean(r.get("address")):
        return None
    # National-level records must not inherit a false local bound. They are resolved
    # by source address when available, otherwise by business name in Korea.
    if clean(r.get("cohort")) in {"national_legislator", "central_executive"}:
        return None
    for k in (clean(r.get("origin")), clean(r.get("jurisdiction"))):
        if k in JURISDICTION_BOUNDS:
            return JURISDICTION_BOUNDS[k]
    return None


def address_tokens(v: str) -> list[str]:
    s = clean_address(v)
    if not s:
        return []
    out = []
    for x in re.findall(r"[가-힣]{2,}(?:특별시|광역시|특별자치시|특별자치도|도|시|군|구)", s):
        if x not in out:
            out.append(x)
    for x in ("서울", "경기", "인천", "충남", "충북", "경남", "경북", "강원", "전남", "전북", "제주"):
        if x in s and x not in out:
            out.append(x)
    return out


def locality_ok(r: dict, result: dict) -> bool:
    lat, lon = result.get("lat"), result.get("lon")
    bounds = source_bounds(r)
    if bounds and isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        xmin, ymin, xmax, ymax = bounds
        return xmin <= lon <= xmax and ymin <= lat <= ymax
    tokens = address_tokens(clean(r.get("address")))
    if not tokens:
        return True
    display = clean(result.get("display_name"))
    return any(t in display for t in tokens)


def name_ok(r: dict, result: dict) -> bool:
    b = r.get("business") or {}
    wanted = [norm_name(b.get("display")), norm_name(r.get("name"))]
    wanted = [x for x in wanted if len(x) >= 2]
    got = norm_name((result.get("result_name") or "") + " " + (result.get("display_name") or ""))
    return bool(got and any(x in got or got in x for x in wanted))


def query_plan(r: dict) -> list[tuple[str, str]]:
    b = r.get("business") or {}
    name = clean(b.get("display") or r.get("name"))
    raw = clean(r.get("name"))
    addr = clean(r.get("address"))
    caddr = clean_address(addr)
    q = clean(r.get("search_query"))
    plan = []
    if addr:
        plan.append((addr, "address"))
    if caddr and caddr != addr:
        plan.append((caddr, "address"))
    if name and caddr:
        plan.append((f"{name} {caddr}", "name_address"))
    if raw and raw != name and caddr:
        plan.append((f"{raw} {caddr}", "name_address"))
    if q:
        plan.append((q, "name_address" if addr else "name"))
    # National supplements often lack a source address. Name-only geocoding is allowed,
    # but still requires a strong exact-name match before coordinates are accepted.
    if name and (not r.get("published_source") or clean(r.get("cohort")) in {"national_legislator", "central_executive"}):
        plan.append((f"{name} 대한민국", "name"))
        if clean(r.get("cohort")) == "national_legislator":
            plan.append((f"{name} 여의도 서울", "name"))
    out, seen = [], set()
    for text, mode in plan:
        text = clean(text)
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append((text, mode))
    return out


def arcgis_candidates(query: str, bounds=None) -> list[dict]:
    params = {
        "SingleLine": query, "f": "json", "countryCode": "KOR", "maxLocations": "10",
        "outFields": "Match_addr,Addr_type,PlaceName",
    }
    if bounds:
        xmin, ymin, xmax, ymax = bounds
        params["location"] = f"{(xmin+xmax)/2},{(ymin+ymax)/2}"
        params["distance"] = "40000"
    req = urllib.request.Request(f"{ARCGIS}?{urllib.parse.urlencode(params)}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    out = []
    for c in obj.get("candidates") or []:
        loc = c.get("location") or {}
        try:
            lat, lon = float(loc["y"]), float(loc["x"])
        except Exception:
            continue
        if not (32 <= lat <= 40 and 123 <= lon <= 133.5):
            continue
        a = c.get("attributes") or {}
        out.append({"lat":lat,"lon":lon,"display_name":c.get("address") or query,"result_name":a.get("PlaceName") or "","query":query,"source":"arcgis","score":float(c.get("score") or 0),"addr_type":a.get("Addr_type") or ""})
    return out


def nominatim_candidates(query: str, bounds=None) -> list[dict]:
    params = {"q":query,"format":"jsonv2","countrycodes":"kr","limit":5,"addressdetails":1,"namedetails":1}
    if bounds:
        xmin, ymin, xmax, ymax = bounds
        params["viewbox"] = f"{xmin},{ymax},{xmax},{ymin}"
        params["bounded"] = 1
    req = urllib.request.Request(f"{NOMINATIM}?{urllib.parse.urlencode(params)}", headers={"User-Agent":USER_AGENT,"Referer":"https://github.com/mrunderdog/executive-dining-seoul"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out=[]
    for x in data:
        try:
            lat,lon=float(x["lat"]),float(x["lon"])
        except Exception:
            continue
        nd=x.get("namedetails") or {}
        out.append({"lat":lat,"lon":lon,"display_name":x.get("display_name", ""),"result_name":nd.get("name") or x.get("name") or "","query":query,"source":"nominatim","osm_type":x.get("type", "")})
    return out


def acceptable(r: dict, result: dict, mode: str) -> bool:
    if not locality_ok(r, result):
        return False
    if result.get("source") == "arcgis":
        score = result.get("score", 0)
        if mode == "address":
            return score >= 80
        if mode == "name_address":
            return score >= 82 and name_ok(r, result)
        # Name-only national matching is intentionally stricter.
        threshold = 94 if clean(r.get("cohort")) in {"national_legislator", "central_executive"} else 90
        return score >= threshold and name_ok(r, result)
    if mode == "name":
        return name_ok(r, result)
    return True


def resolve(r: dict, plan: list[tuple[str,str]]) -> tuple[dict|None,list[str],int]:
    tried, requests = [], 0
    bounds = source_bounds(r)
    for query, mode in plan:
        tried.append(f"arcgis:{query}")
        try:
            candidates = arcgis_candidates(query, bounds); requests += 1
            for result in candidates:
                if acceptable(r, result, mode):
                    result["match_mode"] = mode
                    return result, tried, requests
        except Exception:
            pass
        time.sleep(.12)
    for query, mode in plan:
        if mode == "name" and clean(r.get("address")):
            continue
        tried.append(f"nominatim:{query}")
        try:
            candidates = nominatim_candidates(query, bounds); requests += 1
            for result in candidates:
                if acceptable(r, result, mode):
                    result["match_mode"] = mode
                    return result, tried, requests
        except Exception:
            pass
        time.sleep(1.05)
    return None, tried, requests


def cache_current(old: dict, r: dict, fp: str, retry_all: bool) -> bool:
    if retry_all:
        return False
    base_ok = old.get("geocoder_version") == GEOCODER_VERSION and old.get("fingerprint") == fp
    if not base_ok:
        return False
    if r.get("published_source"):
        return old.get("policy_version") == POLICY_VERSION and (old.get("failed") or isinstance(old.get("lat"), (int, float)))
    return old.get("failed") or isinstance(old.get("lat"), (int, float))


def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("--mode",choices=["auto","initial","regular"],default="auto"); ap.add_argument("--max-new",type=int,default=0); ap.add_argument("--retry-all",action="store_true"); args=ap.parse_args()
    records=merge_extra_published(merge_published_sources(load_payload())).get("records",[])
    cache=load_cache(); items=cache.setdefault("records",{}); todo=[]
    for r in records:
        key=f"{r.get('name','')}|{r.get('origin','')}"; old=items.get(key) if isinstance(items.get(key),dict) else {}; fp=fingerprint(r)
        if cache_current(old,r,fp,args.retry_all):
            continue
        plan=query_plan(r)
        if plan:
            todo.append((key,r,fp,plan))
    if args.max_new>0:
        todo=todo[:args.max_new]
    ok=failed=requests=0
    print(f"geocoder v{GEOCODER_VERSION}/policy{POLICY_VERSION}; records={len(records)}; candidates={len(todo)}")
    for i,(key,r,fp,plan) in enumerate(todo,1):
        result,tried,nreq=resolve(r,plan); requests+=nreq
        stamp={"fingerprint":fp,"geocoder_version":GEOCODER_VERSION,"policy_version":POLICY_VERSION,"tried_queries":tried,"updated_at":datetime.now(timezone.utc).isoformat(timespec="seconds")}
        if result:
            result.update(stamp); items[key]=result; ok+=1
            print(f"[{i}/{len(todo)}] OK {key} -> {result['lat']:.6f},{result['lon']:.6f} ({result['source']}/{result['match_mode']})")
        else:
            items[key]={"failed":True,**stamp}; failed+=1
            print(f"[{i}/{len(todo)}] NO_MATCH {key}")
        save_cache(cache)
    success=sum(isinstance(v,dict) and isinstance(v.get("lat"),(int,float)) for v in items.values())
    save_cache(cache)
    print(json.dumps({"records":len(records),"processed":len(todo),"requests":requests,"ok":ok,"failed":failed,"success_total":success,"coverage":round(success/len(records),4) if records else 0},ensure_ascii=False))


if __name__=="__main__":
    main()
