#!/usr/bin/env python3
"""Opt-in, lossless Uiwang 2026-08/09 PDF reparse into an isolated checkout.

Original attachment URLs and bytes were previously accepted in raw.files but
their 97 observed transactions were lost to NO_HEADER. Only exact verified
original SHA-256 sources may be reprocessed. Never changes historical
transactions or file metadata, and never publishes to the website.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from capital_backfill import canonical_attachment_url
from ingest_council_expense import fetch_binary, workbook_rows, normalize_sheet
from qa_council_publication import git_json
from guard_full_council import check_integrity

EXPECTED = {
    8: ("https://council.uiwang.go.kr/bbsAttachDownload.do?key=42b2c5366f2c05875cf874d5b459ee33bc9aed47fe9a14592bc85b3c52ef51f63a7b570c532bd8e1",
        "e175375b752fdc70b408a5a0dce22cf4317358c4780935496a58ba63b3b4dc58", 4, 42),
    9: ("https://council.uiwang.go.kr/bbsAttachDownload.do?key=1ab017c72c5f4961632c043b0404a1bec512b9811d482bba563e6ae17ae1183cb37d39e5b3a14b42",
        "bc5df5028318f46a62894cd4a08c59472a02a0e105c7599157191ca8d986ba5c", 6, 55),
}


def main():
    raw_path = ROOT / "data/raw/uiwang_expense.json"
    discovery_path = ROOT / "reports/capital-backfill-discovery-uiwang.json"
    baseline = git_json("HEAD", "data/raw/uiwang_expense.json")
    if not baseline or not baseline.get("rows"):
        raise SystemExit("HOLD: missing historical baseline")
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    posts = [p for p in discovery.get("posts", []) if p.get("source") == "uiwang"]
    previous_files = {canonical_attachment_url(x.get("url")): x for x in baseline.get("files", [])}
    current_files = {canonical_attachment_url(x.get("url")): x for x in raw.get("files", [])}
    previous_rows = {x["row_id"]: x for x in baseline.get("rows", [])}
    current_rows = {x["row_id"]: x for x in raw.get("rows", [])}
    if len(previous_rows) != len(baseline["rows"]) or len(current_rows) != len(raw["rows"]):
        raise SystemExit("HOLD: duplicated row identifiers")
    if any(current_rows.get(k) != v for k, v in previous_rows.items()):
        raise SystemExit("HOLD: historical row changed before reparse")
    if any(current_files.get(k) != v for k, v in previous_files.items()):
        raise SystemExit("HOLD: historical attachment record changed before reparse")

    new_rows, evidence = [], []
    for month, (url, digest, expected_pages, expected_rows) in EXPECTED.items():
        canon = canonical_attachment_url(url)
        old_file = previous_files.get(canon)
        current_file = current_files.get(canon)
        if not old_file or not current_file or old_file.get("sha256") != digest:
            raise SystemExit(f"HOLD: baseline file/SHA mismatch {month}")
        if not all(s.get("status") == "NO_HEADER" and not s.get("parsed_rows")
                   for s in old_file.get("sheets", [])):
            raise SystemExit(f"HOLD: original file is not exactly unparsed {month}")
        owners = [p for p in posts if any(canonical_attachment_url(a.get("url")) == canon
                                          for a in p.get("attachments", []))]
        if len(owners) != 1 or owners[0].get("period") != [2026, month, None]:
            raise SystemExit(f"HOLD: no unique exact-period official post {month}")
        post = owners[0]
        blob = fetch_binary(url, post["post_url"])
        observed = hashlib.sha256(blob).hexdigest()
        if observed != digest or not blob.startswith(b"%PDF"):
            raise SystemExit(f"HOLD: source PDF SHA/format mismatch {month}")
        meta = {"source": "uiwang", "region": "경기", "jurisdiction": "의왕시",
                "institution": "의왕시의회", "post_url": post["post_url"],
                "attachment_url": url, "attachment_name": old_file.get("name", ""),
                "attachment_sha256": digest, "period": post["period"],
                "default_role": ""}
        page_summaries = []
        local_rows = []
        for page_name, lines in workbook_rows(blob, old_file.get("name", "") or f"{month}.pdf"):
            normalized, info = normalize_sheet(lines, page_name, meta)
            page_summaries.append(info)
            if info.get("status") != "OK":
                raise SystemExit(f"HOLD: incomplete page {month}/{page_name}: {info}")
            local_rows.extend(normalized)
        if len(page_summaries) != expected_pages or len(local_rows) != expected_rows:
            raise SystemExit(f"HOLD: PDF page/transaction count discrepancy {month}: "
                             f"{len(page_summaries)} pages/{len(local_rows)} rows")
        if any(r["row_id"] in current_rows for r in local_rows):
            raise SystemExit(f"HOLD: 2026-{month:02d} reparse would duplicate/change an existing row")
        for row in local_rows:
            if row["row_id"] in {x["row_id"] for x in new_rows}:
                raise SystemExit("HOLD: duplicate newly reparsed row")
        new_rows.extend(local_rows)
        evidence.append({"month": month, "official_post": post["post_url"],
                         "official_file": url, "sha256": digest,
                         "pages": page_summaries, "new_rows": len(local_rows),
                         "printed_subtotal_sum": sum(x.get("printed_page_total") or 0 for x in page_summaries),
                         "parsed_amount_sum": sum(x["amount"] for x in local_rows)})

    raw["rows"] = sorted([*raw["rows"], *new_rows],
                         key=lambda r: (r.get("used_date") or "", r.get("institution") or "", r.get("row_id") or ""))
    raw["row_count"] = len(raw["rows"])
    integrity = check_integrity("uiwang", raw, baseline)
    if integrity["status"] != "PASS":
        raise SystemExit(f"HOLD: historical integrity failure: {integrity}")
    # The existing approved file records remain exactly unchanged. Store a
    # separate audited reparse ledger instead of falsely modifying original
    # NO_HEADER ingestion metadata.
    path = ROOT / "reports/recovery/uiwang-verified-reparse.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "status": "STAGED_NOT_PUBLISHED", "source": "uiwang",
        "baseline_rows": len(baseline["rows"]),
        "newly_recovered_rows": len(new_rows),
        "total_candidate_rows": len(raw["rows"]),
        "pdfs": evidence, "integrity": integrity,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "STAGED_NOT_PUBLISHED", "recovered_rows": len(new_rows),
                      "total_candidate_rows": len(raw["rows"]), "integrity": "PASS",
                      "evidence_path": str(path)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
