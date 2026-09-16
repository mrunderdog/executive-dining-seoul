#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

from data_io import load_payload

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "site" / "template.html"
MAP_JS = ROOT / "site" / "maplibre.js"
MAP_PATCH_JS = ROOT / "site" / "map_visibility_patch.js"
MAP_CSS = ROOT / "site" / "maplibre.css"
GEO_CACHE = ROOT / "data" / "geocode_cache.json"


def load_geo_cache():
    if not GEO_CACHE.exists():
        return {}
    try:
        obj = json.loads(GEO_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return obj.get("records", obj if isinstance(obj, dict) else {})


def inject_maplibre(html: str) -> str:
    css = MAP_CSS.read_text(encoding="utf-8")
    js = MAP_JS.read_text(encoding="utf-8")
    patch_js = MAP_PATCH_JS.read_text(encoding="utf-8") if MAP_PATCH_JS.exists() else ""

    # Remove the previous Leaflet/markercluster dependencies. The template's layout CSS is kept.
    html = re.sub(r'<link[^>]+leaflet[^>]+>\s*', '', html, flags=re.I)
    html = re.sub(r'<link[^>]+MarkerCluster[^>]+>\s*', '', html, flags=re.I)
    html = html.replace('</head>', '<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@5.7.1/dist/maplibre-gl.css">\n<style>\n' + css + '\n</style>\n</head>')

    # Replace the old Leaflet script block with MapLibre. The dashboard HTML stays unchanged.
    start = html.find('<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>')
    if start < 0:
        raise RuntimeError('Leaflet script marker not found in template')
    end = html.rfind('</body>')
    if end < start:
        raise RuntimeError('body terminator not found')
    replacement = (
        '<script src="https://unpkg.com/maplibre-gl@5.7.1/dist/maplibre-gl.js"></script>\n'
        '<script>\n' + js + '\n</script>\n'
        '<script>\n' + patch_js + '\n</script>\n'
    )
    return html[:start] + replacement + html[end:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=str(ROOT / "index.html"))
    args = ap.parse_args()

    payload = load_payload()
    records = payload.get("records", [])
    if not records:
        raise SystemExit("canonical dataset has no records")

    geo = load_geo_cache()
    coord_count = 0
    for r in records:
        key = f"{r.get('name', '')}|{r.get('origin', '')}"
        g = geo.get(key) or {}
        if isinstance(g.get("lat"), (int, float)) and isinstance(g.get("lon"), (int, float)):
            r["lat"] = float(g["lat"])
            r["lon"] = float(g["lon"])
            coord_count += 1

    stats = payload.get("stats") or {
        "total": len(records),
        "destination": sum(bool(r.get("destination")) for r in records),
        "executive": sum(bool(r.get("executive")) for r in records),
        "both": sum(bool(r.get("destination")) and bool(r.get("executive")) for r in records),
    }
    stats = dict(stats)
    stats["coordinates"] = coord_count
    stats["coordinates_missing"] = len(records) - coord_count
    origins = payload.get("origins") or sorted({r.get("origin", "") for r in records if r.get("origin")})

    html = inject_maplibre(TEMPLATE.read_text(encoding="utf-8"))
    html = html.replace("__DATA__", json.dumps(records, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__STATS__", json.dumps(stats, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__ORIGINS__", json.dumps(origins, ensure_ascii=False, separators=(",", ":")))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"built {out} with {len(records)} records; static coordinates={coord_count}/{len(records)}")


if __name__ == "__main__":
    main()
