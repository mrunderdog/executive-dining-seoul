#!/usr/bin/env python3
"""Build a persistent restaurant coordinate cache for the static site.

Coordinates are resolved during CI, never in the visitor's browser.
The public Nominatim endpoint is used conservatively and every successful result is cached.
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

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "geocode_cache.json"
USER_AGENT = "ExecutiveDiningSeoul/1.2 (+https://github.com/mrunderdog/executive-dining-seoul)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
GEOCODER_VERSION = 2


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
        "provider": "OpenStreetMap Nominatim",
        "policy": "https://operations.osmfoundation.org/policies/nominatim/",
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
    # A surprising number of source rows append a proprietor/person name after a comma.
    s = s.split(",", 1)[0]
    # Normalize artifacts such as '161-0 1층' that frequently fail exact geocoding.
    s = re.sub(r"(?<=\d)-0(?=\s|$)", "", s)
    s = re.sub(r"\b(?:지하\s*)?\d+층\b.*$", "", s)
    s = re.sub(r"\b\d+호\b.*$", "", s)
    return " ".join(s.split()).strip(" ,")


def coarse_address(address: str) -> str:
    s = clean_address(address)
    if not s:
        return ""
    # Keep through the first road/building number and discard unit-level noise.
    m = re.search(r"^(.*?(?:로|길|대로|번길|동|읍|면)\s*\d+(?:-\d+)?)\b", s)
    return m.group(1).strip() if m else s


def fingerprint(r: dict) -> str:
    b = r.get("business") or {}
    raw = "|".join([
        clean_text(r.get("name")),
        clean_text(b.get("display")),
        clean_text(r.get("address")),
        clean_text(r.get("search_query")),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def query_plan(r: dict) -> list[tuple[str, str]]:
    """Return (query, confidence-mode) pairs, de-duplicated in priority order."""
    b = r.get("business") or {}
    name = clean_text(b.get("display") or r.get("name"))
    raw_name = clean_text(r.get("name"))
    address = clean_text(r.get("address"))
    cleaned = clean_address(address)
    coarse = coarse_address(address)
    search_query = clean_text(r.get("search_query"))

    plan: list[tuple[str, str]] = []
    if address:
        plan.append((address, "address"))
    if cleaned and cleaned != address:
        plan.append((cleaned, "address"))
    if coarse and coarse not in {address, cleaned}:
        plan.append((coarse, "address"))
    if name and cleaned:
        plan.append((f"{name} {cleaned}", "name_address"))
    if raw_name and raw_name != name and cleaned:
        plan.append((f"{raw_name} {cleaned}", "name_address"))
    if search_query:
        plan.append((search_query, "name_address" if address else "name"))
    # For missing/broken addresses, a unique POI name can still be resolved safely if
    # Nominatim returns a matching named feature. Do not append the source district, since
    # Destination records may intentionally be outside that district.
    if name:
        plan.append((f"{name} 대한민국", "name"))
    if raw_name and raw_name != name:
        plan.append((f"{raw_name} 대한민국", "name"))

    out: list[tuple[str, str]] = []
    seen = set()
    for q, mode in plan:
        q = clean_text(q)
        k = q.lower()
        if q and k not in seen:
            seen.add(k)
            out.append((q, mode))
    return out


def lookup(query: str) -> dict | None:
    params = urllib.parse.urlencode({
        "q": query,
        "format": "jsonv2",
        "countrycodes": "kr",
        "limit": 1,
        "addressdetails": 1,
        "namedetails": 1,
    })
    req = urllib.request.Request(
        f"{NOMINATIM}?{params}",
        headers={"User-Agent": USER_AGENT, "Referer": "https://github.com/mrunderdog/executive-dining-seoul"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data:
        return None
    x = data[0]
    lat, lon = float(x["lat"]), float(x["lon"])
    if not (32.0 <= lat <= 40.0 and 123.0 <= lon <= 133.5):
        return None
    namedetails = x.get("namedetails") or {}
    result_name = namedetails.get("name") or x.get("name") or ""
    return {
        "lat": lat,
        "lon": lon,
        "display_name": x.get("display_name", ""),
        "result_name": result_name,
        "query": query,
        "source": "nominatim",
        "osm_type": x.get("type", ""),
    }


def name_result_matches(r: dict, result: dict) -> bool:
    b = r.get("business") or {}
    candidates = [normalize_name(b.get("display")), normalize_name(r.get("name"))]
    candidates = [x for x in candidates if len(x) >= 2]
    hay = normalize_name((result.get("result_name") or "") + " " + (result.get("display_name") or ""))
    return bool(hay and any(x in hay or hay in x for x in candidates))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["auto", "initial", "regular"], default="auto")
    ap.add_argument("--max-new", type=int, default=0, help="0 means no explicit cap")
    ap.add_argument("--retry-all", action="store_true", help="retry failed entries even when fingerprint/version did not change")
    args = ap.parse_args()

    payload = load_payload()
    records = payload.get("records", [])
    cache = load_cache()
    items = cache.setdefault("records", {})
    candidates = []

    for r in records:
        key = f"{r.get('name', '')}|{r.get('origin', '')}"
        old = items.get(key) if isinstance(items.get(key), dict) else {}
        fp = fingerprint(r)
        if isinstance(old.get("lat"), (int, float)) and isinstance(old.get("lon"), (int, float)):
            continue
        if (
            not args.retry_all
            and old.get("failed")
            and old.get("geocoder_version") == GEOCODER_VERSION
            and old.get("fingerprint") == fp
        ):
            continue
        plan = query_plan(r)
        if plan:
            candidates.append((key, r, fp, plan))

    if args.max_new > 0:
        candidates = candidates[: args.max_new]

    existing = sum(1 for v in items.values() if isinstance(v, dict) and isinstance(v.get("lat"), (int, float)))
    mode = args.mode
    if mode == "auto":
        mode = "initial" if existing == 0 and len(candidates) >= 20 else "regular"
    # Nominatim's public service asks clients to stay at or below one request per second.
    # CI is single-threaded and persistent cache means subsequent monthly work is tiny.
    delay = 1.15
    print(f"geocode mode={mode}; existing={existing}; records={len(records)}; candidates={len(candidates)}; delay={delay}s")

    ok = failed = requests = 0
    for idx, (key, r, fp, plan) in enumerate(candidates, start=1):
        accepted = None
        tried = []
        for query, confidence_mode in plan:
            tried.append(query)
            try:
                result = lookup(query)
                requests += 1
                if result and (confidence_mode != "name" or name_result_matches(r, result)):
                    result["match_mode"] = confidence_mode
                    accepted = result
                    break
            except Exception as e:
                print(f"[{idx}/{len(candidates)}] QUERY_ERROR {key}: {type(e).__name__}: {e}")
            time.sleep(delay)

        if accepted:
            accepted.update({
                "fingerprint": fp,
                "geocoder_version": GEOCODER_VERSION,
                "tried_queries": tried,
                "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
            items[key] = accepted
            ok += 1
            print(f"[{idx}/{len(candidates)}] OK {key} -> {accepted['lat']:.6f},{accepted['lon']:.6f} ({accepted['match_mode']})")
        else:
            items[key] = {
                "failed": True,
                "fingerprint": fp,
                "geocoder_version": GEOCODER_VERSION,
                "tried_queries": tried,
                "source": "nominatim",
                "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            failed += 1
            print(f"[{idx}/{len(candidates)}] NO_MATCH {key}")
        save_cache(cache)

    save_cache(cache)
    success_total = sum(1 for v in items.values() if isinstance(v, dict) and isinstance(v.get("lat"), (int, float)))
    print(json.dumps({
        "mode": mode,
        "records": len(records),
        "processed": len(candidates),
        "requests": requests,
        "ok": ok,
        "failed": failed,
        "success_total": success_total,
        "coverage": round(success_total / len(records), 4) if records else 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
