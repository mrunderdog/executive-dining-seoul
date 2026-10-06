#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from public_enterprise_discovery import extract_year_month, fetch, looks_file, parse_links

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "public-enterprise-discovery.json"

SOURCE = {
    "key": "kps",
    "institution": "한전KPS",
    "cohort": "public_enterprise_leadership",
    "default_role": "임원",
    "years_lookback": 1,
    "listing": "https://www.kps.co.kr/open_kps/business/boardList.do",
    "metadata_url": "https://www.data.go.kr/data/15151716/fileData.do",
}


def _listing_urls(years: set[int]) -> list[str]:
    return [f"{SOURCE['listing']}?pageIndex={page}" for page in range(1, 6)]


def _is_target(text: str, years: set[int]) -> bool:
    s = " ".join((text or "").split())
    return "업무추진비" in s and any(str(y) in s for y in years)


def _diagnostic_snippets(doc: str, years: set[int]) -> list[str]:
    """Return small HTML contexts around target rows when links are JS/form driven."""
    clean = html.unescape(doc or "")
    snippets = []
    for match in re.finditer(r"업무추진비", clean):
        start = max(0, match.start() - 450)
        end = min(len(clean), match.end() + 650)
        chunk = re.sub(r"\s+", " ", clean[start:end])
        if any(str(y) in chunk for y in years):
            snippets.append(chunk[:1000])
        if len(snippets) >= 3:
            break
    return snippets


def discover(year: int) -> dict:
    years = {year - i for i in range(SOURCE["years_lookback"] + 1)}
    out = {
        "key": SOURCE["key"],
        "institution": SOURCE["institution"],
        "cohort": SOURCE["cohort"],
        "default_role": SOURCE["default_role"],
        "years": sorted(years),
        "pages": [],
        "attachments": [],
        "errors": [],
        "metadata_url": SOURCE["metadata_url"],
        "diagnostics": [],
    }

    listings = _listing_urls(years)
    listing_docs: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=min(5, len(listings))) as pool:
        future_map = {pool.submit(fetch, url): url for url in listings}
        for fut in as_completed(future_map):
            url = future_map[fut]
            try:
                doc = fut.result()
                listing_docs.append((url, doc))
                out["pages"].append(url)
            except Exception as e:
                out["errors"].append(f"listing {url}: {type(e).__name__}: {e}")

    detail_links: list[dict] = []
    direct_files: list[tuple[str, dict]] = []
    seen_detail: set[str] = set()
    seen_file: set[str] = set()

    for listing, doc in listing_docs:
        for link in parse_links(listing, doc):
            label = f"{link.get('text', '')} {link.get('url', '')}".strip()
            if not _is_target(label, years):
                continue
            if looks_file(link):
                if link["url"] not in seen_file:
                    seen_file.add(link["url"])
                    direct_files.append((listing, link))
            elif link["url"] not in seen_detail:
                seen_detail.add(link["url"])
                detail_links.append(link)

    for parent, link in direct_files:
        y, m = extract_year_month(link.get("text", ""))
        out["attachments"].append({**link, "year": y, "month": m, "parent": parent})

    def fetch_detail(link: dict):
        return link, fetch(link["url"])

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(detail_links)))) as pool:
        future_map = {pool.submit(fetch_detail, link): link for link in detail_links}
        for fut in as_completed(future_map):
            link = future_map[fut]
            detail_url = link["url"]
            out["pages"].append(detail_url)
            try:
                _, doc = fut.result()
            except Exception as e:
                out["errors"].append(f"detail {detail_url}: {type(e).__name__}: {e}")
                continue
            for att in parse_links(detail_url, doc):
                if not looks_file(att):
                    continue
                label = f"{link.get('text', '')} {att.get('text', '')}".strip()
                if not _is_target(label, years):
                    continue
                url = att["url"]
                if url in seen_file:
                    continue
                seen_file.add(url)
                y, m = extract_year_month(label)
                out["attachments"].append({
                    "text": label,
                    "url": url,
                    "year": y,
                    "month": m,
                    "parent": detail_url,
                })

    if not out["attachments"]:
        for _, doc in sorted(listing_docs)[:2]:
            out["diagnostics"].extend(_diagnostic_snippets(doc, years))
            if len(out["diagnostics"]) >= 3:
                break

    out["pages"] = list(dict.fromkeys(out["pages"]))
    out["parseable_attachments"] = len(out["attachments"])
    out["status"] = "PARSEABLE_FOUND" if out["attachments"] else (
        "FETCH_FAILED" if out["errors"] and not listing_docs else "NO_FILES_FOUND"
    )
    return out


def main() -> None:
    if not REPORT.exists():
        raise SystemExit("run public_enterprise_discovery.py first")
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    year = int(payload.get("year") or datetime.now().year)
    fresh = discover(year)
    sources = [x for x in payload.get("sources", []) if x.get("key") != SOURCE["key"]]
    sources.append(fresh)
    payload["sources"] = sources
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "key": fresh["key"],
        "status": fresh["status"],
        "pages": len(fresh["pages"]),
        "attachments": len(fresh["attachments"]),
        "errors": fresh["errors"][:5],
        "diagnostics": fresh.get("diagnostics", [])[:3],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
