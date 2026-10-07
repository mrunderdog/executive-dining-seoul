#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import urllib.request
import urllib.parse
import http.cookiejar
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from public_enterprise_discovery import decode, extract_year_month, looks_file, parse_links

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "public-enterprise-discovery.json"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"

SOURCE = {
    "key": "kps",
    "institution": "한전KPS",
    "cohort": "public_enterprise_leadership",
    "default_role": "임원",
    "years_lookback": 1,
    "listing": "https://www.kps.co.kr/web/integrity/clean/expense.do",
    "metadata_url": "https://www.data.go.kr/data/15151716/fileData.do",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
        "Referer": "https://www.kps.co.kr/",
    })
    with urllib.request.urlopen(req, timeout=35) as r:
        return decode(r.read(), r.headers.get_content_charset())


def _listing_urls(years: set[int]) -> list[str]:
    return [SOURCE["listing"]] + [f"{SOURCE['listing']}?pageIndex={page}" for page in range(2, 5)]


def _is_target(text: str, years: set[int]) -> bool:
    s = " ".join((text or "").split())
    return "업무추진비" in s and any(str(y) in s for y in years)


def _diagnostic_snippets(doc: str, years: set[int]) -> list[str]:
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



def _probe_detail(pst_no: str) -> list[str]:
    jar=http.cookiejar.CookieJar()
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req=urllib.request.Request(SOURCE["listing"],headers={
        "User-Agent":BROWSER_UA,
        "Accept":"text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language":"ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
        "Referer":"https://www.kps.co.kr/",
    })
    with opener.open(req,timeout=20) as r:
        listing=decode(r.read(),r.headers.get_content_charset())
    m=re.search(r'name="_csrf"\s+value="([^"]+)"',listing,re.I)
    token=m.group(1) if m else ""
    detail=f"https://www.kps.co.kr/web/Board/{pst_no}/detailView.do?pageIndex=1&menu=2499"
    fields={"pageIndex":"1","menu":"2499"}
    if token:
        fields["_csrf"]=token
    data=urllib.parse.urlencode(fields).encode()
    req=urllib.request.Request(detail,data=data,headers={
        "User-Agent":BROWSER_UA,
        "Accept":"text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language":"ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
        "Referer":SOURCE["listing"],
        "Content-Type":"application/x-www-form-urlencoded",
    })
    with opener.open(req,timeout=20) as r:
        doc=decode(r.read(),r.headers.get_content_charset())
        final_url=r.geturl()
    out=[f"FORM_FIELDS={sorted(fields.items())}",f"DETAIL_URL={final_url}",f"DETAIL_LEN={len(doc)}",f"CSRF={'Y' if token else 'N'}"]
    links=parse_links(final_url,doc)
    out.append(f"DETAIL_LINKS={len(links)}")
    for x in links:
        label=" ".join(((x.get("text") or "")+" "+(x.get("url") or "")).split())
        if any(k in label.lower() for k in ("download","file",".xls",".xlsx","첨부")):
            out.append("LINK="+label[:1800])
    out.append("DETAIL_HTML="+re.sub(r"\\s+"," ",html.unescape(doc)).strip()[:4300])
    for needle in ("다운로드","download","file","xlsx","xls","첨부"):
        for mm in list(re.finditer(needle,doc,re.I))[:3]:
            chunk=re.sub(r"\s+"," ",html.unescape(doc[max(0,mm.start()-700):mm.end()+1500])).strip()
            if chunk not in out:
                out.append(f"DETAIL={chunk[:2600]}")
        if len(out)>=14:
            break
    return out[:14]

def discover(year: int) -> dict:
    years = {year - i for i in range(SOURCE["years_lookback"] + 1)}
    out = {
        "key": SOURCE["key"], "institution": SOURCE["institution"],
        "cohort": SOURCE["cohort"], "default_role": SOURCE["default_role"],
        "years": sorted(years), "pages": [], "attachments": [], "errors": [],
        "metadata_url": SOURCE["metadata_url"], "diagnostics": [],
    }
    listings = _listing_urls(years)
    listing_docs: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=min(5, len(listings))) as pool:
        future_map = {pool.submit(fetch, url): url for url in listings}
        for fut in as_completed(future_map):
            url = future_map[fut]
            try:
                doc = fut.result(); listing_docs.append((url, doc)); out["pages"].append(url)
            except Exception as e:
                out["errors"].append(f"listing {url}: {type(e).__name__}: {e}")

    detail_links: list[dict] = []
    direct_files: list[tuple[str, dict]] = []
    seen_detail: set[str] = set(); seen_file: set[str] = set()
    for listing, doc in listing_docs:
        for link in parse_links(listing, doc):
            label = f"{link.get('text', '')} {link.get('url', '')}".strip()
            if not _is_target(label, years): continue
            if looks_file(link):
                if link["url"] not in seen_file:
                    seen_file.add(link["url"]); direct_files.append((listing, link))
            elif link["url"] not in seen_detail:
                seen_detail.add(link["url"]); detail_links.append(link)

    for parent, link in direct_files:
        y, m = extract_year_month(link.get("text", ""))
        out["attachments"].append({**link, "year": y, "month": m, "parent": parent})

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(detail_links)))) as pool:
        future_map = {pool.submit(fetch, link["url"]): link for link in detail_links}
        for fut in as_completed(future_map):
            link = future_map[fut]; detail_url = link["url"]; out["pages"].append(detail_url)
            try: doc = fut.result()
            except Exception as e:
                out["errors"].append(f"detail {detail_url}: {type(e).__name__}: {e}"); continue
            for att in parse_links(detail_url, doc):
                if not looks_file(att): continue
                label = f"{link.get('text', '')} {att.get('text', '')}".strip()
                if not _is_target(label, years): continue
                url = att["url"]
                if url in seen_file: continue
                seen_file.add(url); y, m = extract_year_month(label)
                out["attachments"].append({"text": label, "url": url, "year": y, "month": m, "parent": detail_url})

    if not out["attachments"]:
        pass

    if not out["attachments"]:
        try:
            out["diagnostics"].extend(_probe_detail("47321"))
        except Exception as e:
            out["diagnostics"].append(f"DETAIL_PROBE_ERROR={type(e).__name__}: {e}")
    out["pages"] = list(dict.fromkeys(out["pages"]))
    out["parseable_attachments"] = len(out["attachments"])
    out["status"] = "PARSEABLE_FOUND" if out["attachments"] else ("FETCH_FAILED" if out["errors"] and not listing_docs else "NO_FILES_FOUND")
    return out


def main() -> None:
    if not REPORT.exists(): raise SystemExit("run public_enterprise_discovery.py first")
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    fresh = discover(int(payload.get("year") or datetime.now().year))
    payload["sources"] = [x for x in payload.get("sources", []) if x.get("key") != SOURCE["key"]] + [fresh]
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"key": fresh["key"], "status": fresh["status"], "pages": len(fresh["pages"]), "attachments": len(fresh["attachments"]), "errors": fresh["errors"][:5], "diagnostics": fresh.get("diagnostics", [])[-20:]}, ensure_ascii=False))


if __name__ == "__main__": main()
