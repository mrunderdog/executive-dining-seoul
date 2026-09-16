#!/usr/bin/env python3
"""Build a persistent restaurant coordinate cache for the static site.

Geocoding happens in CI only. ArcGIS is used as the primary Korean address/POI
resolver and Nominatim as a conservative fallback. Results are cached, versioned,
and locality-checked so a same-name restaurant in another city is not silently used.
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

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "geocode_cache.json"
USER_AGENT = "ExecutiveDiningSeoul/1.3 (+https://github.com/mrunderdog/executive-dining-seoul)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
ARCGIS = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
GEOCODER_VERSION = 3


def load_cache() -> dict:
    if not CACHE.exists():
        return {"meta": {}, "records": {}}
    try:
        obj = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"meta": {}, "records": {}}
    if "records" not in obj:
        obj = {"meta": {}, "records": obj if isinstance(obj, dict) else {}}
    return obj


def save_cache(cache: dict) -> None:
    records = cache.get("records", {})
    success = sum(1 for v in records.values() if isinstance(v, dict) and isinstance(v.get("lat"), (int, float)))
    failed = sum(1 for v in records.values() if isinstance(v, dict) and v.get("failed"))
    cache["meta"] = {
        "providers": ["ArcGIS World Geocoding Service", "OpenStreetMap Nominatim"],
        "geocoder_version": GEOCODER_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "record_count": len(records),
        "success_count": success,
        "failed_count": failed,
    }
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def clean_text(v) -> str:
    return " ".join(str(v or "").replace("\n", " ").split()).strip()


def normalize_name(s: str) -> str:
    s = re.sub(r"\([^)]*\)", "", clean_text(s)).lower()
    s = re.sub(r"(?:주식회사|\(주\)|㈜|유한회사)", "", s)
    return re.sub(r"[^0-9a-z가-힣]", "", s)


def clean_address(address: str) -> str:
    s = clean_text(address)
    if not s:
        return ""
    s = s.replace("@", " ").replace("]", " ").replace("[", " ")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.split(",", 1)[0]
    s = re.sub(r"(?<=\d)-0(?=\s|$)", "", s)
    s = re.sub(r"\b(?:지하\s*)?\d+층\b.*$", "", s)
    s = re.sub(r"\b\d+호\b.*$", "", s)
    return " ".join(s.split()).strip(" ,")


def fingerprint(r: dict) -> str:
    b = r.get("business") or {}
    raw = "|".join([
        clean_text(r.get("name")), clean_text(b.get("display")),
        clean_text(r.get("address")), clean_text(r.get("search_query")),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def locality_tokens(address: str) -> list[str]:
    s = clean_address(address)
    if not s:
        return []
    tokens = []
    for x in re.findall(r"[가-힣]{2,}(?:특별시|광역시|특별자치시|특별자치도|도|시|군|구)", s):
        if x not in {"대한민국"} and x not in tokens:
            tokens.append(x)
    for x in ("서울", "경기", "인천", "충남", "충북", "경남", "경북", "강원", "전남", "전북", "제주"):
        if x in s and x not in tokens:
            tokens.append(x)
    return tokens


def locality_matches(r: dict, display: str) -> bool:
    address = clean_text(r.get("address"))
    tokens = locality_tokens(address)
    if not tokens:
        return True
    return any(t in display for t in tokens)


def query_plan(r: dict) -> list[tuple[str, str]]:
    b = r.get("business") or {}
    name = clean_text(b.get("display") or r.get("name"))
    raw_name = clean_text(r.get("name"))
    address = clean_text(r.get("address"))
    cleaned = clean_address(address)
    search_query = clean_text(r.get("search_query"))
    plan = []
    if address: plan.append((address, "address"))
    if cleaned and cleaned != address: plan.append((cleaned, "address"))
    if name and cleaned: plan.append((f"{name} {cleaned}", "name_address"))
    if raw_name and raw_name != name and cleaned: plan.append((f"{raw_name} {cleaned}", "name_address"))
    if search_query: plan.append((search_query, "name_address" if address else "name"))
    if name: plan.append((f"{name} 대한민국", "name"))
    out, seen = [], set()
    for q, mode in plan:
        q = clean_text(q)
        if q and q.lower() not in seen:
            seen.add(q.lower()); out.append((q, mode))
    return out


def arcgis_lookup(query: str) -> dict | None:
    params = urllib.parse.urlencode({
        "SingleLine": query, "f": "json", "countryCode": "KOR",
        "maxLocations": "1", "outFields": "Match_addr,Addr_type,PlaceName",
    })
    req = urllib.request.Request(f"{ARCGIS}?{params}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    c = (obj.get("candidates") or [None])[0]
    if not c or not c.get("location"):
        return None
    lat, lon = float(c["location"]["y"]), float(c["location"]["x"])
    if not (32.0 <= lat <= 40.0 and 123.0 <= lon <= 133.5):
        return None
    attrs = c.get("attributes") or {}
    return {
        "lat": lat, "lon": lon, "display_name": c.get("address") or query,
        "result_name": attrs.get("PlaceName") or "", "query": query,
        "source": "arcgis", "score": float(c.get("score") or 0),
        "addr_type": attrs.get("Addr_type") or "",
    }


def nominatim_lookup(query: str) -> dict | None:
    params = urllib.parse.urlencode({"q": query, "format": "jsonv2", "countrycodes": "kr", "limit": 1, "addressdetails": 1, "namedetails": 1})
    req = urllib.request.Request(f"{NOMINATIM}?{params}", headers={"User-Agent": USER_AGENT, "Referer": "https://github.com/mrunderdog/executive-dining-seoul"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data: return None
    x = data[0]; lat, lon = float(x["lat"]), float(x["lon"])
    if not (32.0 <= lat <= 40.0 and 123.0 <= lon <= 133.5): return None
    nd = x.get("namedetails") or {}
    return {"lat":lat,"lon":lon,"display_name":x.get("display_name", ""),"result_name":nd.get("name") or x.get("name") or "","query":query,"source":"nominatim","osm_type":x.get("type", "")}


def name_matches(r: dict, result: dict) -> bool:
    b = r.get("business") or {}
    names = [normalize_name(b.get("display")), normalize_name(r.get("name"))]
    names = [x for x in names if len(x) >= 2]
    hay = normalize_name((result.get("result_name") or "") + " " + (result.get("display_name") or ""))
    return bool(hay and any(x in hay or hay in x for x in names))


def acceptable(r: dict, result: dict, mode: str) -> bool:
    if not result: return False
    if not locality_matches(r, result.get("display_name") or ""):
        return False
    if result.get("source") == "arcgis":
        score = result.get("score", 0)
        if mode == "address": return score >= 80
        if mode == "name_address": return score >= 85 and name_matches(r, result)
        return score >= 94 and name_matches(r, result)
    if mode == "name":
        return result.get("osm_type") in {"restaurant","cafe","fast_food","pub","bar","food_court"} and name_matches(r, result)
    return True


def resolve(r: dict, plan: list[tuple[str,str]]) -> tuple[dict|None,list[str],int]:
    tried, requests = [], 0
    for query, mode in plan:
        tried.append(f"arcgis:{query}")
        try:
            result = arcgis_lookup(query); requests += 1
            if acceptable(r, result, mode):
                result["match_mode"] = mode; return result, tried, requests
        except Exception:
            pass
        time.sleep(.12)
    for query, mode in plan:
        if mode == "name" and clean_text(r.get("address")):
            continue
        tried.append(f"nominatim:{query}")
        try:
            result = nominatim_lookup(query); requests += 1
            if acceptable(r, result, mode):
                result["match_mode"] = mode; return result, tried, requests
        except Exception:
            pass
        time.sleep(1.05)
    return None, tried, requests


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["auto","initial","regular"], default="auto")
    ap.add_argument("--max-new", type=int, default=0)
    ap.add_argument("--retry-all", action="store_true")
    args = ap.parse_args()
    payload = merge_published_sources(load_payload()); records = payload.get("records", [])
    cache = load_cache(); items = cache.setdefault("records", {})
    candidates = []
    for r in records:
        key = f"{r.get('name', '')}|{r.get('origin', '')}"; old = items.get(key) if isinstance(items.get(key), dict) else {}; fp = fingerprint(r)
        if isinstance(old.get("lat"), (int,float)) and isinstance(old.get("lon"), (int,float)) and old.get("geocoder_version") == GEOCODER_VERSION and old.get("fingerprint") == fp:
            continue
        if not args.retry_all and old.get("failed") and old.get("geocoder_version") == GEOCODER_VERSION and old.get("fingerprint") == fp:
            continue
        plan = query_plan(r)
        if plan: candidates.append((key,r,fp,plan))
    if args.max_new > 0: candidates = candidates[:args.max_new]
    ok=failed=requests=0
    print(f"geocoder v{GEOCODER_VERSION}; records={len(records)}; candidates={len(candidates)}")
    for idx,(key,r,fp,plan) in enumerate(candidates,1):
        result,tried,nreq = resolve(r,plan); requests += nreq
        if result:
            result.update({"fingerprint":fp,"geocoder_version":GEOCODER_VERSION,"tried_queries":tried,"updated_at":datetime.now(timezone.utc).isoformat(timespec="seconds")})
            items[key]=result; ok+=1
            print(f"[{idx}/{len(candidates)}] OK {key} -> {result['lat']:.6f},{result['lon']:.6f} ({result['source']}/{result['match_mode']})")
        else:
            items[key]={"failed":True,"fingerprint":fp,"geocoder_version":GEOCODER_VERSION,"tried_queries":tried,"updated_at":datetime.now(timezone.utc).isoformat(timespec="seconds")}; failed+=1
            print(f"[{idx}/{len(candidates)}] NO_MATCH {key}")
        save_cache(cache)
    success_total=sum(1 for v in items.values() if isinstance(v,dict) and isinstance(v.get("lat"),(int,float)))
    save_cache(cache)
    print(json.dumps({"records":len(records),"processed":len(candidates),"requests":requests,"ok":ok,"failed":failed,"success_total":success_total,"coverage":round(success_total/len(records),4) if records else 0},ensure_ascii=False))

if __name__ == "__main__": main()
