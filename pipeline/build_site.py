#!/usr/bin/env python3
import argparse
import base64
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "seed" / "current.json.gz.b64"
DATA = ROOT / "data" / "current.json"
TEMPLATE = ROOT / "site" / "template.html"


def load_data():
    if DATA.exists():
        return json.loads(DATA.read_text(encoding="utf-8"))
    raw = base64.b64decode(SEED.read_text(encoding="ascii").strip())
    return json.loads(gzip.decompress(raw).decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=str(ROOT / "index.html"))
    args = ap.parse_args()

    payload = load_data()
    records = payload["records"]
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
