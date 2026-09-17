#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "sources" / "supplemental_registry.json"
REPORTS = ROOT / "reports"
KST = timezone(timedelta(hours=9))
UA = "executive-dining-seoul/2.0 (+GitHub Actions supplemental source check)"


def fetch_text(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        body = r.read()
        try:
            return body.decode(charset, errors="replace"), r.status
        except LookupError:
            return body.decode("utf-8", errors="replace"), r.status


def markers(year: int, month: int):
    quarter = (month - 1) // 3 + 1
    yy = str(year)[-2:]
    return [
        f"{year}년 {month}월", f"{year}년{month}월", f"{year}.{month:02d}",
        f"{year}-{month:02d}", f"{year}/{month:02d}",
        f"{year}년 {quarter}분기", f"{year}년{quarter}분기",
        f"{yy}년 {quarter}분기", f"{yy}년{quarter}분기",
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    ap.add_argument("--month", type=int)
    args = ap.parse_args()

    now = datetime.now(KST)
    if args.year and args.month:
        year, month = args.year, args.month
    else:
        first = now.replace(day=1)
        prev = first - timedelta(days=1)
        year, month = prev.year, prev.month

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    ms = markers(year, month)
    rows = []

    for src in reg.get("sources", []):
        url = src.get("url") or ""
        row = {
            "key": src.get("key"),
            "region": src.get("region"),
            "institution": src.get("institution"),
            "cohort": src.get("cohort"),
            "adapter": src.get("adapter"),
            "verified": bool(src.get("verified")),
            "url": url,
            "status": "DISCOVERY_REQUIRED",
            "detail": src.get("note", ""),
        }
        if not src.get("verified") or not url:
            rows.append(row)
            continue
        try:
            text, status = fetch_text(url)
            found = any(m in text for m in ms)
            row["status"] = "TARGET_PERIOD_VISIBLE" if found else "SOURCE_OK_TARGET_PERIOD_NOT_FOUND"
            row["detail"] = f"HTTP {status}; adapter={src.get('adapter')}"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            row["status"] = "FETCH_FAILED"
            row["detail"] = str(e)[:300]
        rows.append(row)

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_json = REPORTS / f"supplemental-source-status-{year}-{month:02d}.json"
    out_md = REPORTS / f"supplemental-source-status-{year}-{month:02d}.md"
    out_json.write_text(json.dumps({"generated_at": now.isoformat(timespec="seconds"), "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Supplemental source status — {year}-{month:02d}", "",
        "> Supplemental cohorts are monitored separately from the 66 basic councils and are not directly comparable by default.", "",
        "| Region | Institution | Cohort | Adapter | Status | Source |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        src = f"[official]({r['url']})" if r["url"] else "-"
        lines.append(f"| {r['region']} | {r['institution']} | {r['cohort']} | {r['adapter']} | {r['status']} | {src} |")
    lines += ["", "## Publication policy", "", "- `TARGET_PERIOD_VISIBLE` is only a discovery signal.", "- Each source requires a source-specific ingestion adapter and lineage-preserving normalization before publication.", "- `national_legislator` records remain a separate cohort unless a later scoring policy explicitly bridges cohorts."]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_json)


if __name__ == "__main__":
    main()
