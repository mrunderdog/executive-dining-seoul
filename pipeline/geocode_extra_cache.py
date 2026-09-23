#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone

from extra_published import central_records, justice_records, legislator_candidate_records
from geocode_cache import (
    GEOCODER_VERSION,
    POLICY_VERSION,
    fingerprint,
    load_cache,
    query_plan,
    resolve,
    save_cache,
)


def main():
    # Central records are public candidates already. Legislator records here are the
    # top pre-QA candidates so the QA stage can choose the strongest verified 80.
    records = central_records() + justice_records() + legislator_candidate_records(200)
    cache = load_cache()
    items = cache.setdefault("records", {})
    ok = failed = requests = 0
    todo = []

    for r in records:
        key = f"{r.get('name','')}|{r.get('origin','')}"
        fp = fingerprint(r)
        old = items.get(key) if isinstance(items.get(key), dict) else {}
        current = (
            old.get("fingerprint") == fp
            and old.get("geocoder_version") == GEOCODER_VERSION
            and old.get("policy_version") == POLICY_VERSION
            and (old.get("failed") or isinstance(old.get("lat"), (int, float)))
        )
        if current:
            continue
        plan = query_plan(r)
        if plan:
            todo.append((key, r, fp, plan))

    print(f"extra geocoder records={len(records)} candidates={len(todo)}")
    for i, (key, r, fp, plan) in enumerate(todo, 1):
        result, tried, nreq = resolve(r, plan)
        requests += nreq
        stamp = {
            "fingerprint": fp,
            "geocoder_version": GEOCODER_VERSION,
            "policy_version": POLICY_VERSION,
            "tried_queries": tried,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        if result:
            result.update(stamp)
            items[key] = result
            ok += 1
            print(
                f"[{i}/{len(todo)}] OK {key} -> "
                f"{result['lat']:.6f},{result['lon']:.6f} "
                f"({result.get('source')}/{result.get('match_mode')})"
            )
        else:
            items[key] = {"failed": True, **stamp}
            failed += 1
            print(f"[{i}/{len(todo)}] NO_MATCH {key}")
        save_cache(cache)

    save_cache(cache)
    print(json.dumps({
        "records": len(records),
        "processed": len(todo),
        "requests": requests,
        "ok": ok,
        "failed": failed,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
