#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from coordinate_selection import select_coordinate
from data_io import load_payload
from published_sources import merge_published_sources
from extra_published import merge_extra_published
from global_entities import merge_global_entities

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "site" / "template.html"
APP_JS = ROOT / "site" / "app.js"
APP_CSS = ROOT / "site" / "app.css"
GEO_CACHE = ROOT / "data" / "geocode_cache.json"
QUALITY_REPORT = ROOT / "reports" / "quality.json"


def load_geo_cache():
    if not GEO_CACHE.exists():
        return {}
    try:
        obj = json.loads(GEO_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return obj.get("records", obj if isinstance(obj, dict) else {})


def inject_maplibre(html: str) -> str:
    css = APP_CSS.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    html = re.sub(r'<link[^>]+leaflet[^>]+>\s*', '', html, flags=re.I)
    html = re.sub(r'<link[^>]+MarkerCluster[^>]+>\s*', '', html, flags=re.I)
    html = html.replace(
        '</head>',
        '<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@5.7.1/dist/maplibre-gl.css">\n'
        '<style>\n' + css + '\n</style>\n</head>'
    )

    marker = '<!-- APP_RUNTIME -->'
    if marker not in html:
        raise RuntimeError('app runtime marker not found in template')
    replacement = (
        '<script src="https://unpkg.com/maplibre-gl@5.7.1/dist/maplibre-gl.js"></script>\n'
        '<script>\n' + js + '\n</script>\n'
    )
    return html.replace(marker, replacement)


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
    coord_rejected = 0
    for r in records:
        has_address = bool(str(r.get("address") or "").strip())
        source_coord = (
            bool(r.get("source_verified_coordinate"))
            and isinstance(r.get("lat"), (int, float))
            and isinstance(r.get("lon"), (int, float))
        )
        if source_coord:
            r["coordinate_source_key"] = (
                "source:" + str(r.get("source_coordinate_source") or r.get("published_source") or "verified")
            )
            coord_count += 1
            r["location_verification"] = (
                {"grade": "A", "label": "출처 좌표·주소 확인"}
                if has_address else
                {"grade": "B", "label": "출처 좌표 확인 · 주소 미확인"}
            )
            continue

        key, g, meta = select_coordinate(r, geo)
        if g:
            r["lat"] = float(g["lat"])
            r["lon"] = float(g["lon"])
            r["coordinate_source_key"] = key
            coord_count += 1
        if has_address and g:
            r["location_verification"] = {"grade": "A", "label": "주소·위치 확인"}
        elif g:
            r["location_verification"] = {"grade": "B", "label": "위치 확인 · 주소 미확인"}
        else:
            r["location_verification"] = {"grade": "C", "label": "원자료만 · 위치 미확인"}
        coord_rejected += len(meta.get("rejected_candidates") or [])

    stats = dict(payload.get("stats") or {})
    stats.setdefault("total", len(records))
    stats.setdefault("destination", sum(bool(r.get("destination")) for r in records))
    stats.setdefault("executive", sum(bool(r.get("executive")) for r in records))
    stats.setdefault("both", sum(bool(r.get("destination")) and bool(r.get("executive")) for r in records))
    stats["coordinates"] = coord_count
    stats["coordinates_missing"] = len(records) - coord_count
    stats["location_grade_a"] = sum((r.get("location_verification") or {}).get("grade") == "A" for r in records)
    stats["location_grade_b"] = sum((r.get("location_verification") or {}).get("grade") == "B" for r in records)
    stats["location_grade_c"] = sum((r.get("location_verification") or {}).get("grade") == "C" for r in records)
    stats["coordinate_candidates_rejected"] = coord_rejected
    if QUALITY_REPORT.exists():
        try:
            quality = json.loads(QUALITY_REPORT.read_text(encoding="utf-8"))
            source_health = ((quality.get("checks") or {}).get("source_health") or {})
            stats["source_health"] = source_health
            summary = {}
            for row in source_health.values():
                state = str((row or {}).get("diagnosis") or "UNKNOWN")
                summary[state] = summary.get(state, 0) + 1
            stats["source_health_summary"] = summary
        except (OSError, json.JSONDecodeError):
            pass
    origins = payload.get("origins") or sorted({r.get("origin", "") for r in records if r.get("origin")})

    html = inject_maplibre(TEMPLATE.read_text(encoding="utf-8"))
    html = html.replace("__DATA__", json.dumps(records, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__STATS__", json.dumps(stats, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__ORIGINS__", json.dumps(origins, ensure_ascii=False, separators=(",", ":")))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        git_commit = ""
    build_meta = {
        "git_commit": git_commit,
        "dataset_total": len(records),
        "coordinates": coord_count,
        "location_grade_a": stats.get("location_grade_a", 0),
        "location_grade_b": stats.get("location_grade_b", 0),
        "location_grade_c": stats.get("location_grade_c", 0),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    meta_out = out.with_name("build-meta.json")
    meta_out.write_text(json.dumps(build_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    supplements = stats.get("supplemental", 0)
    print(f"built {out} with {len(records)} records (+{supplements} staged public-sector); static coordinates={coord_count}/{len(records)}")
    print(f"build metadata: {meta_out} commit={git_commit[:12] if git_commit else '-'}")


if __name__ == "__main__":
    main()
