#!/usr/bin/env python3
"""October 2026 Uiwang official disclosure: read-only full-scope audit.

Fetches TWO newly published attachments; never writes data/raw or the website.
Does not claim source accuracy merely because parser exit code is zero.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

from capital_backfill import canonical_attachment_url
from guard_full_council import check_integrity
from ingest_council_expense import (
    fetch_binary, workbook_rows, normalize_sheet, infer_pdf_context_role,
    infer_leadership_role, clean_text
)
from qa_council_publication import assess_incremental
from replay_failed_uiwang_pdfs import fnv1a_date_amount, classify_review_flags

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "pipeline/uiwang_official_2026_10_evidence.json"
SOURCE = "uiwang"
MONTH = [2026, 10, None]


def date_like(row):
    if not row:
        return False
    first = clean_text(row[0])
    return bool(re.match(r"^\s*20\d{2}\s*[.]\s*\d{1,2}\s*[.]?\s*\d{1,2}\s*[.]?(?:\s|$)", first)
                or re.match(r"^\s*20\d{2}-\d{1,2}-\d{1,2}(?:\s|$)", first))


def audit_october(baseline, discovery, evidence, *, download=fetch_binary, read_sheets=workbook_rows):
    failures = []
    candidates = []
    files = []
    per_file = []
    existing_ids = {r.get("row_id"): r for r in baseline.get("rows") or []}
    existing_files = {canonical_attachment_url(f.get("url")): f
                      for f in baseline.get("files") or []}
    if baseline.get("source") != SOURCE or len(existing_ids) != len(baseline.get("rows") or []):
        failures.append("baseline_invalid")
    for item in evidence.get("items") or []:
        url = item["url"]
        key = canonical_attachment_url(url)
        rec = {"url": url, "category": item["category"],
               "expected_count": item["official_transaction_count"],
               "expected_total_krw": item["official_total_krw"],
               "pages": [], "sha256": None}
        per_file.append(rec)
        if not key or key in existing_files:
            failures.append("october_url_not_new_or_noncanonical")
            continue
        try:
            blob = download(url, evidence["official_post"])
            digest = hashlib.sha256(blob).hexdigest()
            rec["sha256"] = digest
            rec["bytes"] = len(blob)
            if not blob.startswith(b"%PDF"):
                failures.append("official_response_not_pdf")
                continue
            staged = []
            carried_role = ""
            for sheet_name, source_rows in read_sheets(blob, item["name"]):
                observed_dates = sum(date_like(row) for row in source_rows)
                page_role = infer_pdf_context_role(source_rows) if sheet_name.startswith("pdf-page-") else ""
                if page_role:
                    carried_role = page_role
                meta = {"source": SOURCE, "region": "경기", "jurisdiction": "의왕시",
                        "institution": "의왕시의회", "post_url": evidence["official_post"],
                        "attachment_url": url, "attachment_name": item["name"],
                        "attachment_sha256": digest, "period": MONTH,
                        "default_role": page_role or carried_role
                        or infer_leadership_role(item["name"])}
                parsed, info = normalize_sheet(source_rows, sheet_name, meta)
                rec["pages"].append({"sheet": sheet_name, "observed_dated_rows": observed_dates,
                                     "parsed_rows": len(parsed), "status": info.get("status"),
                                     "unparsed_transaction_like_rows": info.get("unparsed_transaction_like_rows", 0),
                                     "printed_date_format_anomalies": [
                                         {"source_row": i + 1, "source_text": clean_text(row[0])}
                                         for i, row in enumerate(source_rows) if date_like(row)
                                         and not re.match(r"^\s*2026\.\s*10\.\s*\d{1,2}\.", clean_text(row[0]))
                                     ][:20]})
                if (info.get("status") != "OK"
                    or observed_dates != len(parsed)
                    or info.get("unparsed_transaction_like_rows", 0)):
                    failures.append("october_page_parse_gap")
                staged.extend(parsed)
            rec["parsed_count"] = len(staged)
            rec["parsed_total_krw"] = sum(int(r["amount"] or 0) for r in staged)
            rec["date_amount_fingerprint"] = fnv1a_date_amount(staged)
            target_sum = sum(item.get("official_section_totals_krw") or [])
            if (len(staged) != item["official_transaction_count"]
                or rec["parsed_total_krw"] != item["official_total_krw"]
                or rec["parsed_total_krw"] != target_sum
                or rec["date_amount_fingerprint"] != item["date_amount_fnv1a32"]):
                failures.append("october_official_count_amount_or_date_mismatch")
            for row in staged:
                rid = row.get("row_id")
                if not rid or rid in existing_ids:
                    failures.append("october_row_conflicts_with_baseline")
                else:
                    existing_ids[rid] = row
                    candidates.append(row)
            files.append({"name": item["name"], "title": "2026년 10월 업무추진비 사용내역 공개",
                          "url": url, "bytes": len(blob), "sha256": digest,
                          "sheets": [{"sheet": v["sheet"], "status": v["status"],
                                      "parsed_rows": v["parsed_rows"],
                                      "unparsed_transaction_like_rows": v["unparsed_transaction_like_rows"]}
                                     for v in rec["pages"]]})
        except Exception as exc:
            rec["error_type"] = type(exc).__name__
            failures.append("october_download_or_parse_exception")
    if len(per_file) != 2 or len(files) != 2:
        failures.append("missing_october_official_attachments")

    october_post = {
        "source": SOURCE, "region": "경기", "jurisdiction": "의왕시",
        "institution": "의왕시의회", "title": "2026년 10월 업무추진비 사용내역 공개",
        "post_url": evidence["official_post"], "period": MONTH,
        "attachments": [{"url": item["url"], "text": item["name"]}
                        for item in evidence.get("items") or []]
    }
    old_posts = discovery.get("posts") or []
    combined_discovery = {**discovery, "posts": [*old_posts, october_post]}
    proposed = {**baseline,
                "rows": [*(baseline.get("rows") or []), *candidates],
                "files": [*(baseline.get("files") or []), *files]}
    integrity = check_integrity(SOURCE, proposed, baseline)
    if integrity["status"] != "PASS":
        failures.extend(integrity["failures"])
    qa = assess_incremental(SOURCE, proposed, combined_discovery, baseline, discovery)
    if qa["status"] != "PUBLISH_READY":
        failures += qa["failures"] or ["october_strict_qa_not_ready"]

    flags = classify_review_flags(candidates)
    # DO NOT mark published/recommendable even if financial QA passes:
    # October dining classification and complete discovery remain separate gates.
    report = {
        "source": SOURCE, "period": "2026-10", "source_published": evidence["published_on"],
        "baseline_rows": len(baseline.get("rows") or []),
        "baseline_files": len(baseline.get("files") or []),
        "new_official_files": len(files),
        "candidate_rows": len(candidates),
        "candidate_total_krw": sum(int(r.get("amount") or 0) for r in candidates),
        "file_results": per_file, "strict_qa": qa, "integrity": integrity,
        "dining_review_flags": flags,
        "status": "READY_FOR_CLASSIFICATION" if not failures else "HOLD",
        "failures": sorted(set(failures)),
        "publish": False,
        "note": "Live October discovery and complete restaurant eligibility must be independently approved before publishing.",
    }
    return report, candidates


def main():
    base_file = ROOT / "data/raw/uiwang_expense.json"
    baseline_bytes = base_file.read_bytes()
    baseline = json.loads(baseline_bytes)
    discovery = json.loads((ROOT / "reports/capital-backfill-discovery-uiwang.json").read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    report, rows = audit_october(baseline, discovery, evidence)
    report["baseline_sha256"] = hashlib.sha256(baseline_bytes).hexdigest()
    if base_file.read_bytes() != baseline_bytes:
        raise RuntimeError("baseline modified during October audit")
    out = ROOT / "reports/recovery/uiwang-october"
    out.mkdir(parents=True, exist_ok=True)
    (out / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "candidate_rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "candidate_rows": report["candidate_rows"],
        "total_krw": report["candidate_total_krw"],
        "failures": report["failures"], "publish": False,
        "report": str(out / "audit.json")
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
