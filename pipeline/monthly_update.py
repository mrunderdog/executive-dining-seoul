#!/usr/bin/env python3
import argparse
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "sources" / "registry.json"
REPORTS = ROOT / "reports"
KST = timezone(timedelta(hours=9))


def previous_month(now):
    first = now.replace(day=1)
    prev_last = first - timedelta(days=1)
    return prev_last.year, prev_last.month


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "executive-dining-seoul/1.0 (+GitHub Actions monthly source check)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        body = r.read()
        try:
            return body.decode(charset, errors="replace"), r.status
        except LookupError:
            return body.decode("utf-8", errors="replace"), r.status


def month_markers(year, month):
    return [
        f"{year}년 {month}월",
        f"{year}년{month}월",
        f"{year}.{month:02d}",
        f"{year}-{month:02d}",
        f"{year}/{month:02d}",
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    ap.add_argument("--month", type=int)
    args = ap.parse_args()

    now = datetime.now(KST)
    year, month = (args.year, args.month) if args.year and args.month else previous_month(now)
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    markers = month_markers(year, month)

    rows = []
    for src in reg["sources"]:
        district = src["district"]
        url = src.get("url")
        if not src.get("verified") or not url:
            rows.append({"district": district, "status": "DISCOVERY_REQUIRED", "url": url or "", "detail": src.get("note", "official listing URL not verified")})
            continue
        try:
            text, status = fetch_text(url)
            found = any(m in text for m in markers)
            rows.append({
                "district": district,
                "status": "TARGET_MONTH_VISIBLE" if found else "SOURCE_OK_TARGET_MONTH_NOT_FOUND",
                "url": url,
                "detail": f"HTTP {status}; markers={','.join(markers)}",
            })
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            rows.append({"district": district, "status": "FETCH_FAILED", "url": url, "detail": str(e)[:300]})

    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"source-status-{year}-{month:02d}.md"
    lines = [
        f"# Monthly source status — {year}-{month:02d}",
        "",
        f"Generated: {now.isoformat(timespec='seconds')}",
        "",
        "## Summary",
        "",
    ]
    for k in sorted(counts):
        lines.append(f"- **{k}**: {counts[k]}")
    lines += [
        "",
        "> This report is a source-discovery gate. A source being visible does **not** mean its PDF/XLSX rows were automatically ingested yet.",
        "> Only district adapters that explicitly parse and normalize official expense rows may update `data/current.json`.",
        "",
        "## Districts",
        "",
        "| District | Status | Detail | Source |",
        "|---|---|---|---|",
    ]
    for row in rows:
        source = f"[official]({row['url']})" if row["url"] else "-"
        detail = row["detail"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {row['district']} | {row['status']} | {detail} | {source} |")

    lines += [
        "",
        "## Publish gate",
        "",
        "- `TARGET_MONTH_VISIBLE` only means the official listing appears to contain the target month.",
        "- Raw expense ingestion, entity matching, geocoding, scoring and manual review are separate gates.",
        "- Do not publish a newly discovered restaurant without source lineage and a stable entity match.",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out)
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
