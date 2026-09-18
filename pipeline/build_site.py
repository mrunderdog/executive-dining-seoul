#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

from data_io import load_payload
from published_sources import merge_published_sources
from extra_published import merge_extra_published
from global_entities import merge_global_entities

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "site" / "template.html"
MAP_JS = ROOT / "site" / "maplibre.js"
MAP_PATCH_JS = ROOT / "site" / "map_visibility_patch.js"
MAP_CSS = ROOT / "site" / "maplibre.css"
THEME_CSS = ROOT / "site" / "flying_papers.css"
UI_PATCH_JS = ROOT / "site" / "ui_patch.js"
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
    theme_css = THEME_CSS.read_text(encoding="utf-8") if THEME_CSS.exists() else ""
    js = MAP_JS.read_text(encoding="utf-8")
    patch_js = MAP_PATCH_JS.read_text(encoding="utf-8") if MAP_PATCH_JS.exists() else ""
    ui_patch_js = UI_PATCH_JS.read_text(encoding="utf-8") if UI_PATCH_JS.exists() else ""

    html = re.sub(r'<link[^>]+leaflet[^>]+>\s*', '', html, flags=re.I)
    html = re.sub(r'<link[^>]+MarkerCluster[^>]+>\s*', '', html, flags=re.I)
    html = html.replace(
        '</head>',
        '<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@5.7.1/dist/maplibre-gl.css">\n'
        '<style>\n' + css + '\n' + theme_css + '\n</style>\n</head>'
    )

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
        '<script>\n' + ui_patch_js + '\n</script>\n'
    )
    return html[:start] + replacement + html[end:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=str(ROOT / "index.html"))
    args = ap.parse_args()

    payload = merge_global_entities(merge_extra_published(merge_published_sources(load_payload())))
    records = payload.get("records", [])
    if not records:
        raise SystemExit("published dataset has no records")

    geo = load_geo_cache()
    coord_count = 0
    for r in records:
        candidates = list(r.get("source_keys") or [])
        candidates.append(f"{r.get('name', '')}|{r.get('origin', '')}")
        g = {}
        for key in candidates:
            row = geo.get(key) or {}
            if isinstance(row.get("lat"), (int, float)) and isinstance(row.get("lon"), (int, float)):
                g = row
                break
        if isinstance(g.get("lat"), (int, float)) and isinstance(g.get("lon"), (int, float)):
            r["lat"] = float(g["lat"])
            r["lon"] = float(g["lon"])
            r["coordinate_source_key"] = key
            coord_count += 1

    stats = dict(payload.get("stats") or {})
    stats.setdefault("total", len(records))
    stats.setdefault("destination", sum(bool(r.get("destination")) for r in records))
    stats.setdefault("executive", sum(bool(r.get("executive")) for r in records))
    stats.setdefault("both", sum(bool(r.get("destination")) and bool(r.get("executive")) for r in records))
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
    supplements = stats.get("supplemental", 0)
    print(f"built {out} with {len(records)} records (+{supplements} staged public-sector); static coordinates={coord_count}/{len(records)}")


if __name__ == "__main__":
    main()
