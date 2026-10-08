#!/usr/bin/env python3
"""Staging-only ingestion of verifiable education/police executive spending.

Not wired to the public candidate feed until disclosure formats and role
attribution pass source-specific review. Last-good rows survive fetch failures.
"""
from __future__ import annotations

import argparse
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from ingest_central_executive_expense import parse_attachment
from leadership_scope import classify_leadership_title, valid_transaction, actor_explicit_in_target
from venue_eligibility import is_non_venue_merchant
from gyeonggi_education_pdf import parse as parse_gyeonggi_pdf
from incheon_education_xlsx import parse as parse_incheon_xlsx

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sources" / "education_police_registry.json"
DISCOVERY = ROOT / "reports" / "education-police-source-probe.json"
RAW = ROOT / "data" / "raw" / "education_police_expense_staging.json"

def process(parsed: list[dict], source: dict, post: dict, download_url: str) -> tuple[list[dict], dict]:
    """Enforce transaction and official-position lineage before retaining a row."""
    verified = classify_leadership_title(post.get("title", ""), source["cohort"])
    stats = {"input": len(parsed), "accepted": 0, "rejected": 0}
    if not verified or verified["tier"] != post.get("tier"):
        stats["rejected"] = len(parsed)
        return [], stats
    rows = []
    for incoming in parsed:
        r = dict(incoming)
        r.update({
            "source_key": source["key"],
            "institution": source["institution"],
            "cohort": source["cohort"],
            "role": verified["role"],
            "role_tier": verified["tier"],
            "role_source": "posting_title",
            "source_detail_url": post["detail_url"],
            "source_url": download_url,
            "publication_status": "STAGING_ONLY",
            "actor_presence": "EXPLICIT" if actor_explicit_in_target(verified["role"], r.get("target")) else "UNCONFIRMED",
        })
        if not valid_transaction(r, set(source["official_hosts"])) or is_non_venue_merchant(r.get("merchant")):
            stats["rejected"] += 1
            continue
        r["row_id"] = hashlib.sha256("|".join(str(r.get(k) or "") for k in (
            "source_key", "role", "used_date", "merchant", "amount", "source_url", "source_sheet", "source_row"
        )).encode("utf-8")).hexdigest()[:24]
        rows.append(r)
    stats["accepted"] = len(rows)
    return rows, stats

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-attachments", type=int, default=30)
    args = ap.parse_args()
    if not DISCOVERY.exists():
        raise SystemExit("run education_police_source_probe.py first")
    registry = {s["key"]: s for s in json.loads(SOURCE.read_text(encoding="utf-8"))["sources"]}
    discoveries = json.loads(DISCOVERY.read_text(encoding="utf-8")).get("sources", [])
    previous = json.loads(RAW.read_text(encoding="utf-8")) if RAW.exists() else {}
    retained = {r["row_id"]: r for r in previous.get("rows", []) if r.get("row_id")}
    fetches = 0
    results = []
    errors = []
    for entry in discoveries:
        key = entry.get("key")
        src = registry.get(key)
        if not src or src.get("publish"):
            continue
        for post in entry.get("posts") or []:
            role = classify_leadership_title(post.get("title", ""), src["cohort"])
            if not role or not post.get("detail_url"):
                continue
            for att in post.get("attachments") or []:
                if fetches >= max(0, args.max_attachments):
                    break
                url = att.get("url") or ""
                name = att.get("name") or ""
                if not url or not name:
                    continue
                fetches += 1
                attachment = {"url": url, "download_url": url, "text": name,
                              "parent": post["detail_url"]}
                source_input = {"key": key, "institution": src["institution"],
                                "cohort": src["cohort"], "default_role": role["role"]}
                if key == "gyeonggi_education" and url.lower().split("?")[0].endswith(".pdf"):
                    parsed, info, error = parse_gyeonggi_pdf(url, post["detail_url"])
                elif key == "incheon_education" and url.lower().split("?")[0].endswith(".xlsx"):
                    parsed, info, error = parse_incheon_xlsx(url,post["detail_url"])
                else:
                    parsed, info, error = parse_attachment(source_input, attachment)
                if error:
                    errors.append({"key": key, "url": url, "error": str(error)[:250]})
                    continue
                accepted, stats = process(parsed, src, post, url)
                for row in accepted:
                    retained[row["row_id"]] = row
                results.append({"key": key, "url": url, "stats": stats, "parse_info": info})
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "publication_enabled": False,
        "rows": sorted(retained.values(), key=lambda r: (r.get("used_date") or "", r["row_id"])),
        "files_attempted": fetches, "file_results": results,
        "errors": errors[:100],
        "retained_last_good_count": len(previous.get("rows", [])),
    }
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"staged_rows": len(doc["rows"]), "attempted": fetches, "parsed_files": len(results),
                      "errors": len(errors), "publication_enabled": False}, ensure_ascii=False))
if __name__ == "__main__":
    main()
