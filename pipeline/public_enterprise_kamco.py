#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from public_enterprise_discovery import extract_year_month, fetch, looks_file, parse_links

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "public-enterprise-discovery.json"

KEY = "kamco"
INSTITUTION = "한국자산관리공사"
# Confirmed official detail page. KAMCO exposes previous/next monthly posts on each detail page,
# so traversing that chain is more reliable than its list-page pagination markup.
SEED = "https://www.kamco.or.kr/portal/bbs/view.do?bIdx=22548&mId=0601060603&ptIdx=479"


def _bidx(url: str) -> str:
    try:
        return (parse_qs(urlparse(url).query).get("bIdx") or [""])[0]
    except Exception:
        return ""


def discover(year: int) -> dict:
    years = {year, year - 1}
    out = {
        "key": KEY,
        "institution": INSTITUTION,
        "cohort": "public_enterprise_leadership",
        "default_role": "임원",
        "years": sorted(years),
        "pages": [],
        "attachments": [],
        "errors": [],
    }
    queue = deque([SEED])
    seen_pages: set[str] = set()
    seen_files: set[str] = set()

    # One seed around 2025-04 plus previous/next traversal covers both 2025 and 2026.
    # Cap traversal to protect the monthly workflow from accidental graph expansion.
    while queue and len(seen_pages) < 40:
        url = queue.popleft()
        bid = _bidx(url) or url
        if bid in seen_pages:
            continue
        seen_pages.add(bid)
        out["pages"].append(url)
        try:
            doc = fetch(url)
        except Exception as e:
            out["errors"].append(f"detail {url}: {type(e).__name__}: {e}")
            continue

        links = parse_links(url, doc)
        for link in links:
            text = " ".join((link.get("text") or "").split())
            href = link.get("url") or ""
            label = f"{text} {href}".strip()

            # Follow adjacent KAMCO expense detail posts even when link text is only 이전글/다음글.
            if "view.do" in href and "ptIdx=479" in href:
                child = _bidx(href) or href
                if child not in seen_pages:
                    queue.append(href)

            if not looks_file(link):
                continue
            # Attachment text on KAMCO detail pages contains the monthly title.
            y, m = extract_year_month(label)
            if y not in years:
                continue
            if href in seen_files:
                continue
            seen_files.add(href)
            out["attachments"].append({
                "text": text,
                "url": href,
                "year": y,
                "month": m,
                "parent": url,
            })

    out["parseable_attachments"] = len(out["attachments"])
    out["status"] = "PARSEABLE_FOUND" if out["attachments"] else (
        "FETCH_FAILED" if out["errors"] and len(out["pages"]) <= 1 else "NO_FILES_FOUND"
    )
    return out


def main():
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    fresh = discover(int(payload.get("year") or datetime.now().year))
    payload["sources"] = [x for x in payload.get("sources", []) if x.get("key") != KEY] + [fresh]
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "key": KEY,
        "status": fresh["status"],
        "pages": len(fresh["pages"]),
        "attachments": len(fresh["attachments"]),
        "errors": fresh["errors"][:5],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
