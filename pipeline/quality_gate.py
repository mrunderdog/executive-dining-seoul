#!/usr/bin/env python3
import base64
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "current.json"
SEED = ROOT / "seed" / "current.json.gz.b64"


def load_payload():
    if DATA.exists():
        return json.loads(DATA.read_text(encoding="utf-8"))
    raw = gzip.decompress(base64.b64decode(SEED.read_text(encoding="ascii").strip()))
    return json.loads(raw.decode("utf-8"))


def fail(msg):
    print(f"FAIL: {msg}")
    return 1


def main():
    p = load_payload()
    records = p.get("records")
    if not isinstance(records, list) or len(records) < 50:
        return fail("records missing or unexpectedly small")

    seen = set()
    origins = set()
    problems = []
    for i, r in enumerate(records):
        name = str(r.get("name") or "").strip()
        origin = str(r.get("origin") or "").strip()
        if not name or not origin:
            problems.append(f"row {i}: missing name/origin")
            continue
        k = (name, origin)
        if k in seen:
            problems.append(f"duplicate key: {name} / {origin}")
        seen.add(k)
        origins.add(origin)

        if r.get("type") not in {"destination", "executive", "both"}:
            problems.append(f"{name}: invalid type")
        ev = r.get("evidence") or {}
        for f in ("visits", "spend", "people"):
            v = ev.get(f, 0)
            if not isinstance(v, (int, float)) or v < 0:
                problems.append(f"{name}: invalid evidence.{f}")
        if not isinstance(r.get("business"), dict):
            problems.append(f"{name}: missing business object")
        if r.get("destination"):
            s = r["destination"].get("score")
            if not isinstance(s, (int, float)) or not 0 <= s <= 100:
                problems.append(f"{name}: invalid destination score")
        if r.get("executive"):
            s = r["executive"].get("score")
            if not isinstance(s, (int, float)) or not 0 <= s <= 100:
                problems.append(f"{name}: invalid executive score")

    if len(origins) < 20:
        problems.append(f"origin coverage too small: {len(origins)}")
    if problems:
        print("\n".join("FAIL: " + x for x in problems[:50]))
        if len(problems) > 50:
            print(f"... and {len(problems)-50} more")
        return 1

    print(f"PASS: {len(records)} records / {len(origins)} origins / {len(seen)} unique keys")
    return 0


if __name__ == "__main__":
    sys.exit(main())
