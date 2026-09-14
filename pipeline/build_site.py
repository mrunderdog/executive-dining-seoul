#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from data_io import load_payload

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "site" / "template.html"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=str(ROOT / "index.html"))
    args = ap.parse_args()

    payload = load_payload()
    records = payload.get("records", [])
    if not records:
        raise SystemExit("canonical dataset has no records")

    stats = payload.get("stats") or {
        "total": len(records),
        "destination": sum(bool(r.get("destination")) for r in records),
        "executive": sum(bool(r.get("executive")) for r in records),
        "both": sum(bool(r.get("destination")) and bool(r.get("executive")) for r in records),
    }
    origins = payload.get("origins") or sorted({r.get("origin", "") for r in records if r.get("origin")})

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__DATA__", json.dumps(records, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__STATS__", json.dumps(stats, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__ORIGINS__", json.dumps(origins, ensure_ascii=False, separators=(",", ":")))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"built {out} with {len(records)} records")


if __name__ == "__main__":
    main()
