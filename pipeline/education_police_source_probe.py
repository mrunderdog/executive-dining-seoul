#!/usr/bin/env python3
"""Read-only official source discovery for education and police leadership expenses.

The probe does not turn a listing into a restaurant event. Evidence requires
an official transaction attachment, title-derived role and parsed venue.
"""
from __future__ import annotations
import argparse
import html
import json
import re
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from leadership_scope import classify_leadership_title, clean

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "sources" / "education_police_registry.json"
REPORT = ROOT / "reports" / "education-police-source-probe.json"
UA = "Mozilla/5.0 (compatible; ExecutiveDining/1.0; public-open-data-research)"
TYPES = (".pdf", ".xlsx", ".xls", ".hwp", ".hwpx", ".csv")

def police_same_host_fallback(url: str) -> str:
    """Known official servlet-context alternative; never switch host/scheme."""
    p=urllib.parse.urlsplit(url)
    if p.scheme != "https" or p.hostname != "www.police.go.kr":
        return ""
    if not p.path.startswith("/user/bbs/"):
        return ""
    return urllib.parse.urlunsplit((p.scheme,p.netloc,"/BZRKZR"+p.path,p.query,""))

def fetch(url: str, timeout: int = 18) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        # Some police.go.kr servlet URLs respond with repeated HTTP 307
        # redirects. Retry only the known same-origin /BZRKZR context.
        fallback = police_same_host_fallback(url) if exc.code == 307 else ""
        if not fallback:
            raise
        response = urllib.request.urlopen(
            urllib.request.Request(fallback,headers={"User-Agent":UA,"Accept-Language":"ko-KR,ko;q=0.9"}),
            timeout=timeout
        )
    with response:
        if response.status != 200:
            raise ValueError("HTTP " + str(response.status))
        raw = response.read(3_000_000)
        charset = response.headers.get_content_charset()
    for encoding in [charset, "utf-8", "cp949", "euc-kr"]:
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")

class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current = None
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.current = {"attrs": dict(attrs), "text": ""}
    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data
    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.current["text"] = clean(html.unescape(self.current["text"]))
            self.links.append(self.current)
            self.current = None

def absolute_safe_link(base: str, value: str, allowed_hosts: set[str]) -> str:
    s = html.unescape(value or "").strip()
    if not s or s.startswith(("javascript:", "#", "data:")):
        return ""
    full = urllib.parse.urljoin(base, s)
    p = urllib.parse.urlsplit(full)
    host = (p.hostname or "").lower()
    if p.scheme != "https" or not any(host == h or host.endswith("." + h) for h in allowed_hosts):
        return ""
    return full

def extract_post_id(attributes: dict, family: str) -> str:
    combined = " ".join(str(v or "") for v in attributes.values())
    if family == "police":
        m = re.search(r"q_bbscttSn[^0-9]{0,8}([0-9]{10,20})", combined)
        if m:
            return m.group(1)
        m = re.search(r"(20\d{15})", combined)
        return m.group(1) if m else ""
    m = re.search(r"nttSn[^0-9]{0,8}([0-9]{5,12})", combined)
    if m:
        return m.group(1)
    m = re.search(r"(?<!\d)(\d{5,12})(?!\d)", combined)
    return m.group(1) if m else ""

def detail_url(listing: str, post_id: str, family: str) -> str:
    if family == "police":
        return "https://www.police.go.kr/user/bbs/BD_selectBbs.do?q_bbsCode=1025&q_bbscttSn=" + post_id
    qs = urllib.parse.parse_qs(urllib.parse.urlsplit(listing).query)
    params = {"bbsId": qs.get("bbsId", [""])[0], "mi": qs.get("mi", [""])[0], "nttSn": post_id}
    base = urllib.parse.urlsplit(listing)
    return urllib.parse.urlunsplit((base.scheme, base.netloc, base.path.replace("selectNttList.do", "selectNttInfo.do"), urllib.parse.urlencode(params), ""))

def discover_post_links(page: str, listing: str, cohort: str, family: str, allowed_hosts: set[str]) -> list[dict]:
    links = Anchors()
    links.feed(page)
    found = {}
    for a in links.links:
        title = clean(a.get("text"))
        role = classify_leadership_title(title, cohort)
        if not role:
            continue
        attrs = a["attrs"]
        href = absolute_safe_link(listing, attrs.get("href", ""), allowed_hosts)
        post_id = extract_post_id(attrs, family)
        if href and ("selectNttInfo" in href or "BD_selectBbs.do" in href):
            url = href
        elif post_id:
            url = detail_url(listing, post_id, family)
        else:
            url = ""
        key = url or title
        found[key] = {"title": title, "role": role["role"], "tier": role["tier"], "detail_url": url,
                      "discovery_status": "DETAIL_LINK_FOUND" if url else "TITLE_ONLY"}
    return list(found.values())

def discover_attachments(page: str, url: str, allowed_hosts: set[str]) -> list[dict]:
    parser = Anchors()
    parser.feed(page)
    found = {}
    for a in parser.links:
        label = clean(a["text"])
        value = a["attrs"].get("href", "")
        link = absolute_safe_link(url, value, allowed_hosts)
        if not link:
            continue
        # For download APIs without extensions, require file-like anchor text.
        looks_file = any(t in label.lower() or t in urllib.parse.urlsplit(link).path.lower() for t in TYPES)
        if looks_file:
            found[link] = {"name": label, "url": link}
    # GOE official board renders an opaque download JS token, but the adjacent
    # preview action contains an explicit HTTPS resource URL. Capture only those
    # exact, same-domain PDF/file URLs; never synthesize an arbitrary download URL.
    for a in parser.links:
        onclick = str(a["attrs"].get("onclick") or "")
        match = re.search(r"https://[^\s'<>]+[.](?:pdf|xlsx?|hwpx?|csv)", onclick, re.I)
        if not match:
            continue
        link = absolute_safe_link(url, match.group(0), allowed_hosts)
        if link:
            found[link] = {"name": link.rsplit("/", 1)[-1], "url": link}
    return list(found.values())

def attachment_diagnostics(page: str) -> list[dict]:
    parser = Anchors()
    parser.feed(page)
    likely = []
    for item in parser.links:
        attrs = item["attrs"]
        label = clean(item["text"])
        if any(t in (label + " " + str(attrs)).lower() for t in ("pdf", "xlsx", "다운로드", "첨부", "filedown", "download")):
            likely.append({"label": label[:115], "href": str(attrs.get("href") or "")[:250],
                           "onclick": str(attrs.get("onclick") or "")[:250]})
    return likely[:18]

def probe_source(source: dict, max_details: int = 12) -> dict:
    key = source["key"]
    family = "police" if key == "national_police" else "education"
    hosts = set(source["official_hosts"])
    found = [{"title": seed["title"], "role": seed["role"], "tier": seed["tier"],
              "detail_url": seed["url"], "discovery_status": "VERIFIED_DETAIL_SEED"}
             for seed in source.get("verified_detail_urls", [])]
    queues = []
    errors = []
    board_status = []
    for board in source.get("boards", []):
        url = board["url"]
        try:
            page = fetch(url)
            posts = discover_post_links(page, url, source["cohort"], family, hosts)
            # ICE intermittently serves a truncated page with just one recent
            # listing. Retry the exact official board before deciding that
            # all other published months and senior roles have disappeared.
            if key == "incheon_education" and len(posts) < 3:
                by_url={p.get("detail_url") or p["title"]:p for p in posts}
                for _ in range(3):
                    try:
                        page_retry=fetch(url)
                        for item in discover_post_links(page_retry,url,source["cohort"],family,hosts):
                            by_url[item.get("detail_url") or item["title"]]=item
                    except Exception as retry_exc:
                        errors.append(f"retry {url}: {type(retry_exc).__name__}: {str(retry_exc)[:100]}")
                posts=list(by_url.values())
            queues.append(list(posts))
            board_status.append({"url": url, "status": "OK", "posts": len(posts)})
        except Exception as exc:
            board_status.append({"url": url, "status": "FETCH_FAILED", "posts": 0})
            errors.append(f"{url}: {type(exc).__name__}: {str(exc)[:140]}")
    # Round-robin boards so limited probes include head, deputy and bureau director,
    # instead of exhausting the superintendent board before inspecting other roles.
    while any(queues):
        for queue in queues:
            if queue:
                found.append(queue.pop(0))
    uniq = {}
    for entry in found:
        uniq[entry.get("detail_url") or entry["title"]] = entry
    found = list(uniq.values())
    tried = 0
    for entry in found:
        if tried >= max_details:
            break
        url = entry.get("detail_url")
        if not url:
            continue
        tried += 1
        try:
            page = fetch(url)
            entry["attachments"] = discover_attachments(page, url, hosts)
            entry["detail_fetch"] = "OK"
            if not entry["attachments"]:
                entry["link_debug"] = attachment_diagnostics(page)
        except Exception as exc:
            entry["detail_fetch"] = "FETCH_FAILED"
            entry["attachments"] = []
            errors.append(f"{url}: {type(exc).__name__}: {str(exc)[:140]}")
    return {
        "key": key, "institution": source["institution"], "cohort": source["cohort"],
        "status": "DISCOVERY_ONLY", "publish": False,
        "boards": board_status, "posts": found,
        "titles_scoped": len(found), "details_fetched": tried,
        "attachments_linked": sum(len(x.get("attachments") or []) for x in found),
        "errors": errors[:30],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-details", type=int, default=12)
    args = ap.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    results = [probe_source(s, max_details=max(0, args.max_details)) for s in registry["sources"]]
    doc = {"generated_at": datetime.now(timezone.utc).isoformat(), "publication_enabled": False, "sources": results}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([{"key": s["key"], "titles_scoped": s["titles_scoped"],
       "details_fetched": s["details_fetched"], "attachments_linked": s["attachments_linked"],
       "errors": s["errors"][:2]} for s in results], ensure_ascii=False))
if __name__ == "__main__":
    main()
