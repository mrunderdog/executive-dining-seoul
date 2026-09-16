#!/usr/bin/env python3
"""Discover official expense posts/attachments for first Capital Area adapters.

This intentionally stages source lineage first. Attachment discovery is automatic; row parsing is
handled separately and may only publish after schema/quality checks.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
UA = "ExecutiveDiningSeoul/1.0 (+https://github.com/mrunderdog/executive-dining-seoul)"


@dataclass
class Source:
    key: str
    region: str
    jurisdiction: str
    institution: str
    listing_template: str
    max_pages: int
    kind: str


SOURCES = [
    Source("suwon", "경기", "수원시", "수원특례시의회", "https://council.suwon.go.kr/kr/costBBS.do?flag=all&page={page}", 20, "monthly"),
    Source("goyang", "경기", "고양시", "고양특례시의회", "https://www.goyangcouncil.go.kr/kr/costBBS.do?flag=all&page={page}", 10, "quarterly"),
    Source("bupyeong", "인천", "부평구", "부평구의회", "https://council.icbp.go.kr/kr/data/bbs?bbs_id=expense&page={page}", 15, "monthly"),
]


class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        a = dict(attrs)
        self.stack.append({"href": a.get("href", ""), "text": []})

    def handle_data(self, data):
        if self.stack:
            self.stack[-1]["text"].append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.stack:
            x = self.stack.pop()
            x["text"] = " ".join("".join(x["text"]).split())
            self.anchors.append(x)


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        charset = r.headers.get_content_charset() or "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def anchors(url: str, text: str):
    p = AnchorParser(); p.feed(text)
    out = []
    for a in p.anchors:
        href = html.unescape(a.get("href", "")).strip()
        if not href or href.startswith("javascript:") or href == "#":
            continue
        out.append({"text": a.get("text", ""), "url": urllib.parse.urljoin(url, href)})
    return out


def title_period(title: str):
    m = re.search(r"(20\d{2})\s*년\s*(\d{1,2})\s*월", title)
    if m:
        return int(m.group(1)), int(m.group(2)), None
    m = re.search(r"(?:(20)?(\d{2}))\s*년\s*([1-4])\s*분기", title)
    if m:
        year = int((m.group(1) or "20") + m.group(2))
        return year, None, int(m.group(3))
    return None


def period_overlaps(period, since: tuple[int, int], until: tuple[int, int]):
    if not period:
        return False
    y, m, q = period
    if q:
        lo = (y, 1 + (q - 1) * 3); hi = (y, q * 3)
    else:
        lo = hi = (y, m)
    return not (hi < since or lo > until)


def post_like(a, src: Source):
    t, u = a["text"], a["url"]
    if "업무추진비" not in t:
        return False
    if src.key in {"suwon", "goyang"}:
        return "costBBSview" in u
    if src.key == "bupyeong":
        return "expense" in u and ("reform=view" in u or "bbs" in u)
    return True


def attachment_like(a):
    t, u = a["text"].lower(), a["url"].lower()
    return (".xlsx" in t or ".xls" in t or ".xlsx" in u or ".xls" in u or "download" in u) and "업무추진비" not in t


def discover_source(src: Source, since, until):
    seen_posts = set(); posts = []
    for page in range(1, src.max_pages + 1):
        url = src.listing_template.format(page=page)
        try:
            doc = fetch_text(url)
        except Exception as e:
            posts.append({"source": src.key, "listing_url": url, "error": f"listing {type(e).__name__}: {e}"})
            break
        for a in anchors(url, doc):
            if not post_like(a, src):
                continue
            period = title_period(a["text"])
            if not period_overlaps(period, since, until) or a["url"] in seen_posts:
                continue
            seen_posts.add(a["url"])
            row = {
                "source": src.key, "region": src.region, "jurisdiction": src.jurisdiction,
                "institution": src.institution, "title": a["text"], "period": period,
                "post_url": a["url"], "attachments": [],
            }
            try:
                detail = fetch_text(a["url"])
                row["attachments"] = [x for x in anchors(a["url"], detail) if attachment_like(x)]
            except Exception as e:
                row["error"] = f"detail {type(e).__name__}: {e}"
            posts.append(row)
    return posts


def ym(s: str):
    y, m = s.split("-")
    return int(y), int(m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2024-12")
    ap.add_argument("--until", default=datetime.now().strftime("%Y-%m"))
    ap.add_argument("--source", choices=[s.key for s in SOURCES])
    args = ap.parse_args()
    since, until = ym(args.since), ym(args.until)
    selected = [s for s in SOURCES if not args.source or s.key == args.source]
    rows = []
    for src in selected:
        rows.extend(discover_source(src, since, until))

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_json = REPORTS / "capital-backfill-discovery.json"
    out_md = REPORTS / "capital-backfill-discovery.md"
    result = {"generated_at": datetime.now().isoformat(timespec="seconds"), "since": args.since, "until": args.until, "sources": [s.key for s in selected], "posts": rows}
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"# Capital area backfill discovery — {args.since} ~ {args.until}", ""]
    for src in selected:
        rr = [x for x in rows if x.get("source") == src.key]
        good = [x for x in rr if x.get("post_url")]
        attachments = sum(len(x.get("attachments", [])) for x in good)
        lines += [f"## {src.institution}", "", f"- Posts: {len(good)}", f"- Attachment links: {attachments}", ""]
        for x in good[:30]:
            lines.append(f"- [{x['title']}]({x['post_url']}) — attachments {len(x.get('attachments', []))}")
        lines.append("")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"posts": sum(1 for x in rows if x.get("post_url")), "attachments": sum(len(x.get("attachments", [])) for x in rows)}, ensure_ascii=False))
    print(out_json)


if __name__ == "__main__":
    main()
