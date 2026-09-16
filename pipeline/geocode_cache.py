#!/usr/bin/env python3
"""Build a persistent restaurant coordinate cache for the static site.

The public Nominatim service is used only for small cached maintenance work.
- Initial one-time seed: <= 1 request/sec.
- Recurring maintenance: <= 4 requests/minute and only uncached addresses.
See https://operations.osmfoundation.org/policies/nominatim/
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from data_io import load_payload

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "geocode_cache.json"
USER_AGENT = "ExecutiveDiningSeoul/1.0 (+https://github.com/mrunderdog/executive-dining-seoul)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"


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
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache["meta"] = {
        "provider": "OpenStreetMap Nominatim",
        "policy": "https://operations.osmfoundation.org/policies/nominatim/",
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "record_count": len(cache.get("records", {})),
    }
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def lookup(query: str) -> dict | None:
    params = urllib.parse.urlencode({"q": query, "format": "jsonv2", "countrycodes": "kr", "limit": 1, "addressdetails": 0})
    req = urllib.request.Request(
        f"{NOMINATIM}?{params}",
        headers={"User-Agent": USER_AGENT, "Referer": "https://github.com/mrunderdog/executive-dining-seoul"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data:
        return None
    x = data[0]
    return {"lat": float(x["lat"]), "lon": float(x["lon"]), "display_name": x.get("display_name", ""), "query": query, "source": "nominatim"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["auto", "initial", "regular"], default="auto")
    ap.add_argument("--max-new", type=int, default=0, help="0 means no explicit cap")
    args = ap.parse_args()

    payload = load_payload()
    records = payload.get("records", [])
    cache = load_cache()
    items = cache.setdefault("records", {})
    candidates = []
    for r in records:
        key = f"{r.get('name', '')}|{r.get('origin', '')}"
        if key in items and isinstance(items[key].get("lat"), (int, float)):
            continue
        address = str(r.get("address") or "").strip()
        if address:
            candidates.append((key, address))
    if args.max_new > 0:
        candidates = candidates[: args.max_new]

    existing = sum(1 for v in items.values() if isinstance(v, dict) and isinstance(v.get("lat"), (int, float)))
    mode = args.mode
    if mode == "auto":
        mode = "initial" if existing == 0 and len(candidates) >= 20 else "regular"
    delay = 1.10 if mode == "initial" else 15.5
    print(f"geocode mode={mode}; existing={existing}; new={len(candidates)}; delay={delay}s")

    ok = failed = 0
    for idx, (key, query) in enumerate(candidates, start=1):
        try:
            result = lookup(query)
            if result:
                items[key] = result
                ok += 1
                print(f"[{idx}/{len(candidates)}] OK {key} -> {result['lat']:.6f},{result['lon']:.6f}")
            else:
                items[key] = {"failed": True, "query": query, "source": "nominatim"}
                failed += 1
                print(f"[{idx}/{len(candidates)}] NO_MATCH {key}")
        except Exception as e:
            failed += 1
            print(f"[{idx}/{len(candidates)}] ERROR {key}: {type(e).__name__}: {e}")
        save_cache(cache)
        if idx != len(candidates):
            time.sleep(delay)
    save_cache(cache)
    print(json.dumps({"mode": mode, "requested": len(candidates), "ok": ok, "failed": failed, "cached": len(items)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
