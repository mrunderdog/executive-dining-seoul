#!/usr/bin/env python3
import argparse
import json
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
    req = urllib.request.Request(url, headers={"User-Agent": "executive-dining-seoul/2.0 (+GitHub Actions monthly source check)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        body = r.read()
        try:
            return body.decode(charset, errors="replace"), r.status
        except LookupError:
            return body.decode("utf-8", errors="replace"), r.status


def month_markers(year, month):
    quarter = (month - 1) // 3 + 1
    yy = str(year)[-2:]
    return [
        f"{year}년 {month}월",
        f"{year}년{month}월",
        f"{year}.{month:02d}",
        f"{year}-{month:02d}",
        f"{year}/{month:02d}",
        f"{year}년 {quarter}분기",
        f"{year}년{quarter}분기",
        f"{yy}년 {quarter}분기",
        f"{yy}년{quarter}분기",
    ]


def source_name(src):
    return src.get("institution") or src.get("district") or src.get("jurisdiction") or "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    ap.add_argument("--month", type=int)
    ap.add_argument("--region", choices=["서울", "경기", "인천"])
    args = ap.parse_args()

    now = datetime.now(KST)
    year, month = (args.year, args.month) if args.year and args.month else previous_month(now)
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    markers = month_markers(year, month)

    rows = []
    for src in reg["sources"]:
        region = src.get("region") or "서울"
        if args.region and region != args.region:
            continue
        jurisdiction = src.get("jurisdiction") or src.get("district") or ""
        institution = source_name(src)
        level = src.get("jurisdiction_level", "basic_council")
        url = src.get("url")
        if not src.get("verified") or not url:
            rows.append({
                "region": region,
                "jurisdiction": jurisdiction,
                "institution": institution,
                "level": level,
                "status": "DISCOVERY_REQUIRED",
                "url": url or "",
                "detail": src.get("note", "official listing URL not verified"),
            })
            continue
        try:
            text, status = fetch_text(url)
            found = any(m in text for m in markers)
            rows.append({
                "region": region,
                "jurisdiction": jurisdiction,
                "institution": institution,
                "level": level,
                "status": "TARGET_PERIOD_VISIBLE" if found else "SOURCE_OK_TARGET_PERIOD_NOT_FOUND",
                "url": url,
                "detail": f"HTTP {status}; markers={','.join(markers)}",
            })
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            rows.append({
                "region": region,
                "jurisdiction": jurisdiction,
                "institution": institution,
                "level": level,
                "status": "FETCH_FAILED",
                "url": url,
                "detail": str(e)[:300],
            })

    counts = {}
    region_counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        region_counts.setdefault(row["region"], {})
        region_counts[row["region"]][row["status"]] = region_counts[row["region"]].get(row["status"], 0) + 1

    REPORTS.mkdir(parents=True, exist_ok=True)
    suffix = f"-{args.region}" if args.region else ""
    out = REPORTS / f"source-status-{year}-{month:02d}{suffix}.md"
    lines = [
        f"# Capital Region monthly source status — {year}-{month:02d}",
        "",
        f"Generated: {now.isoformat(timespec='seconds')}",
        "",
        "## Summary",
        "",
    ]
    for k in sorted(counts):
        lines.append(f"- **{k}**: {counts[k]}")
    lines += ["", "## By region", ""]
    for region in ("서울", "경기", "인천"):
        rc = region_counts.get(region, {})
        if not rc:
            continue
        lines.append(f"### {region}")
        for k in sorted(rc):
            lines.append(f"- {k}: {rc[k]}")
        lines.append("")

    lines += [
        "> This report is a source-discovery gate. A source being visible does **not** mean its PDF/XLSX rows were automatically ingested yet.",
        "> Quarterly sources are treated as visible when the target month's quarter marker is present.",
        "> Only explicit parsers that normalize official expense rows may update the published dataset.",
        "",
        "## Institutions",
        "",
        "| Region | Jurisdiction | Institution | Level | Status | Detail | Source |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        source = f"[official]({row['url']})" if row["url"] else "-"
        detail = row["detail"].replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {row['region']} | {row['jurisdiction']} | {row['institution']} | {row['level']} | {row['status']} | {detail} | {source} |"
        )

    lines += [
        "",
        "## Publish gate",
        "",
        "- `TARGET_PERIOD_VISIBLE` only means the official listing appears to contain the target month or quarter.",
        "- Raw expense ingestion, entity matching, geocoding, scoring and manual review are separate gates.",
        "- Do not publish a newly discovered restaurant without source lineage and a stable entity match.",
        "- Regional councils are not mixed into basic-council rankings by default.",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out)
    print(json.dumps({"summary": counts, "by_region": region_counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
