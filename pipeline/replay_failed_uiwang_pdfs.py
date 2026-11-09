#!/usr/bin/env python3
"""Read-only, digest-pinned replay of previously failed Uiwang official PDFs.

This script intentionally does NOT replace data/raw or the published site.
All parsed candidate rows, page evidence, and a fail-closed audit are staged
under reports/recovery for independent review. A passing run is NOT approval
to publish; the full source reconciliation remains a separate gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from capital_backfill import canonical_attachment_url
from guard_full_council import check_integrity
from ingest_council_expense import (
    fetch_binary, infer_leadership_role, infer_pdf_context_role,
    normalize_sheet, uiwang_pdf_transaction_like, valid_transaction_merchant,
    workbook_rows,
)
from qa_council_publication import period_bounds

ROOT = Path(__file__).resolve().parents[1]
BAD_SHEETS = {"NO_HEADER", "ROW_PARSE_GAPS"}


def period_key(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return ""
    year, month, _ = value
    if not isinstance(year, int) or not isinstance(month, int) or not 1 <= month <= 12:
        return ""
    return f"{year:04d}-{month:02d}"


def replay(source, baseline, discovery, since, until, *, download=fetch_binary,
           read_sheets=workbook_rows):
    """Return an audit and an isolated list of candidate new rows.

    No baseline record or file is modified. Every replayed file must have a
    committed SHA256 and a matching URL in the official discovery snapshot.
    """
    if source != "uiwang":
        raise ValueError("the replay adapter has only been validated for uiwang")
    if not (since <= until and len(since) == len(until) == 7):
        raise ValueError("expected YYYY-MM start/end")
    if baseline.get("source") != source:
        raise ValueError("baseline source mismatch")

    records = baseline.get("rows") or []
    existing_files = baseline.get("files") or []
    old_ids = {row.get("row_id"): row for row in records}
    file_map = {}
    failures = []
    for item in existing_files:
        identity = canonical_attachment_url(item.get("url"))
        if not identity or identity in file_map:
            failures.append("invalid_or_duplicate_baseline_file_url")
        else:
            file_map[identity] = item
    if not records or not existing_files or len(old_ids) != len(records):
        failures.append("missing_or_duplicate_baseline_rows_or_files")

    targeted = {}
    selected_posts = [
        p for p in discovery.get("posts", [])
        if p.get("source") == source and since <= period_key(p.get("period")) <= until
    ]
    if not selected_posts:
        failures.append("no_official_posts_in_target_period")
    for post in selected_posts:
        if not post.get("post_url") or post.get("error"):
            failures.append("official_discovery_incomplete")
        if not post.get("attachments"):
            failures.append("official_post_without_attachments")
        for attachment in post.get("attachments") or []:
            identity = canonical_attachment_url(attachment.get("url"))
            if not identity:
                failures.append("noncanonical_official_attachment")
                continue
            baseline_file = file_map.get(identity)
            if baseline_file is None:
                # Do not silently ignore newly discovered attachments when
                # auditing completeness of a selected official period.
                failures.append("official_attachment_missing_from_baseline")
                continue
            if not any((sheet.get("status") in BAD_SHEETS)
                       for sheet in baseline_file.get("sheets") or []):
                continue
            if identity in targeted:
                if targeted[identity]["post"]["post_url"] != post["post_url"]:
                    failures.append("attachment_linked_from_multiple_posts")
                continue
            targeted[identity] = {"post": post, "file": baseline_file,
                                  "url": attachment["url"]}
    if not targeted:
        failures.append("no_failed_pdfs_selected")

    candidate = []
    replayed = []
    seen = dict(old_ids)
    for identity, selected in sorted(targeted.items()):
        post, prior, url = selected["post"], selected["file"], selected["url"]
        result = {"url": url, "source_post_url": post["post_url"],
                  "source_period": post.get("period"), "name": prior.get("name"),
                  "expected_sha256": prior.get("sha256"),
                  "previous_sheets": [
                      {"sheet": x.get("sheet"), "status": x.get("status")}
                      for x in prior.get("sheets") or []],
                  "pages": [], "new_rows": 0}
        replayed.append(result)
        expected = prior.get("sha256") or ""
        if not isinstance(expected, str) or len(expected) != 64:
            result["failure"] = "invalid_baseline_sha256"
            failures.append(result["failure"])
            continue
        try:
            blob = download(url, post["post_url"])
        except Exception as exc:
            result["failure"] = "download_error"
            result["error_type"] = type(exc).__name__
            failures.append("download_error")
            continue
        actual = hashlib.sha256(blob).hexdigest()
        result["actual_sha256"] = actual
        result["bytes"] = len(blob)
        if actual != expected:
            result["failure"] = "official_attachment_sha256_changed"
            failures.append(result["failure"])
            continue
        if not blob.startswith(b"%PDF"):
            result["failure"] = "baseline_attachment_not_pdf"
            failures.append(result["failure"])
            continue

        carried_role = ""
        staged = []
        try:
            for sheet_name, rows in read_sheets(blob, prior.get("name") or url):
                if not sheet_name.startswith("pdf-page-"):
                    failures.append("unexpected_attachment_sheet_type")
                    result["pages"].append({"sheet": sheet_name, "status": "UNSUPPORTED"})
                    continue
                page_role = infer_pdf_context_role(rows)
                if page_role:
                    carried_role = page_role
                meta = {
                    "source": source,
                    "region": post["region"],
                    "jurisdiction": post["jurisdiction"],
                    "institution": post["institution"],
                    "post_url": post["post_url"],
                    "attachment_url": url,
                    "attachment_name": prior.get("name") or "",
                    "attachment_sha256": actual,
                    "period": post.get("period"),
                    "default_role": (page_role or carried_role
                                     or infer_leadership_role(prior.get("name") or "")
                                     or infer_leadership_role(post.get("title") or "")),
                }
                normalized, info = normalize_sheet(rows, sheet_name, meta)
                dated_count = sum(bool(uiwang_pdf_transaction_like(row)) for row in rows)
                page_info = {"sheet": sheet_name, "status": info.get("status"),
                             "printed_dated_rows": dated_count,
                             "parsed_rows": len(normalized),
                             "unparsed_transaction_like_rows": info.get("unparsed_transaction_like_rows", 0),
                             "source_lines_sample": [
                                 {"row": i + 1, "cells": [str(x) for x in row[:7]]}
                                 for i, row in enumerate(rows) if uiwang_pdf_transaction_like(row)
                             ][:3]}
                result["pages"].append(page_info)
                if (info.get("status") != "OK" or len(normalized) != dated_count
                    or info.get("unparsed_transaction_like_rows", 0)):
                    # A page whose empty status has not been justified
                    # by original-document evidence is NOT certified empty.
                    failures.append("unresolved_pdf_page")
                staged.extend(normalized)
        except Exception as exc:
            result["failure"] = "pdf_parse_exception"
            result["error_type"] = type(exc).__name__
            failures.append("pdf_parse_exception")
            continue
        if not result["pages"]:
            result["failure"] = "pdf_without_extracted_pages"
            failures.append(result["failure"])
        for row in staged:
            rid = row.get("row_id")
            if not rid or rid in seen:
                if rid in seen and seen[rid] == row:
                    # Already published rows must not be claimed as new.
                    continue
                failures.append("duplicate_or_conflicting_transaction_row")
                continue
            bounds = period_bounds(row.get("source_period"))
            try:
                when = date.fromisoformat(str(row.get("used_date") or ""))
            except ValueError:
                when = None
            amount = row.get("amount")
            if not (
                row.get("source_key") == source
                and canonical_attachment_url(row.get("source_attachment_url")) == identity
                and row.get("source_post_url") == post["post_url"]
                and bounds and when and bounds[0] <= when <= bounds[1]
                and valid_transaction_merchant(row.get("merchant"))
                and isinstance(amount, (int, float)) and not isinstance(amount, bool)
                and 0 < amount < 50_000_000
            ):
                failures.append("staged_row_failed_strict_date_amount_lineage")
                continue
            seen[rid] = row
            candidate.append(row)
            result["new_rows"] += 1

    proposed = {**baseline, "rows": [*records, *candidate]}
    integrity = check_integrity(source, proposed, baseline)
    if integrity["status"] != "PASS":
        failures.extend(integrity["failures"])
    report = {
        "source": source, "period": {"from": since, "to": until},
        "baseline": {"rows": len(records), "files": len(existing_files)},
        "selected_failed_files": len(targeted),
        "reparsed_files": replayed,
        "staged_new_rows": len(candidate),
        "integrity": integrity,
        "status": "READY_FOR_REVIEW" if not failures else "HOLD",
        "failures": sorted(set(failures)),
        "publish": False,
        "notes": "Staging only. No raw JSON or website changes. Human PDF/page reconciliation is still required.",
    }
    return report, candidate



def fnv1a_date_amount(rows):
    """Fingerprint sorted independently observed transaction dates and amounts."""
    keys = sorted(f'{r["used_date"]}|{int(r["amount"])}' for r in rows)
    h = 0x811c9dc5
    for character in "\n".join(keys):
        h = ((h ^ ord(character)) * 0x01000193) & 0xffffffff
    return f"{h:08x}"


def independent_source_evidence_check(candidate_rows, evidence):
    """Cross-check candidate date/amount records against the official source ledger."""
    issues, per_period = [], []
    for item in evidence.get("files", []):
        month = item["period"]
        selected = [r for r in candidate_rows if period_key(r.get("source_period")) == month]
        amount_total = sum(int(r["amount"]) for r in selected)
        fp = fnv1a_date_amount(selected)
        printed_sections = sum(item.get("printed_section_totals_krw", []))
        matched = (len(selected) == item["transaction_count"]
                   and amount_total == item["transaction_total_krw"]
                   and amount_total == printed_sections
                   and fp == item["transaction_date_amount_fnv1a32"])
        if not matched:
            issues.append("official_source_date_amount_or_subtotal_mismatch:" + month)
        per_period.append({"period": month, "rows": len(selected),
                           "amount_krw": amount_total,
                           "date_amount_fingerprint": fp,
                           "expected_rows": item["transaction_count"],
                           "expected_amount_krw": item["transaction_total_krw"],
                           "expected_fingerprint": item["transaction_date_amount_fnv1a32"],
                           "matched": matched})
    candidate_periods = {period_key(row.get("source_period")) for row in candidate_rows}
    official_periods = {f["period"] for f in evidence.get("files", [])}
    if candidate_periods != official_periods:
        issues.append("official_source_period_coverage_mismatch")
    if len(evidence.get("files", [])) != 3:
        issues.append("incomplete_official_source_evidence")
    return {"status": "PASS" if not issues else "HOLD",
            "months": per_period, "failures": issues}


def classify_review_flags(rows):
    """Report unresolved dining/recommendation cases without allocating shared amounts."""
    out = []
    for r in rows:
        merchant = str(r.get("merchant") or "")
        purpose = str(r.get("purpose") or "")
        flags = []
        if "," in merchant or "，" in merchant:
            flags.append("MULTI_MERCHANT_SHARED_AMOUNT")
        if any(token in merchant for token in ("쿠팡", "백운인쇄기획사", "GS25", "고천화원", "요양원")):
            flags.append("NON_DINING_MERCHANT_REVIEW")
        if any(token in purpose for token in ("명함 제작", "화분 구입", "위문품 구입", "격려 물품 구입")):
            if "NON_DINING_MERCHANT_REVIEW" not in flags:
                flags.append("NON_DINING_PURPOSE_REVIEW")
        if flags:
            out.append({"row_id": r["row_id"], "source_period": r.get("source_period"),
                        "source_sheet": r.get("source_sheet"), "source_row": r.get("source_row"),
                        "date": r.get("used_date"), "merchant": merchant,
                        "amount_krw": r.get("amount"), "flags": flags})
    return out


def output_path(path):
    out = Path(path).resolve()
    sandbox = (ROOT / "reports" / "recovery").resolve()
    if not out.is_relative_to(sandbox):
        raise ValueError("audit outputs must remain under reports/recovery")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["uiwang"], default="uiwang")
    parser.add_argument("--since", default="2026-07")
    parser.add_argument("--until", default="2026-09")
    parser.add_argument("--output-dir", default=str(ROOT / "reports/recovery/uiwang-replay"))
    parser.add_argument("--fail-on-hold", action="store_true")
    args = parser.parse_args()
    out_dir = output_path(args.output_dir)
    raw_path = ROOT / "data/raw" / f"{args.source}_expense.json"
    discovery_path = ROOT / "reports" / f"capital-backfill-discovery-{args.source}.json"
    baseline_bytes = raw_path.read_bytes()
    baseline = json.loads(baseline_bytes)
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    report, rows = replay(args.source, baseline, discovery, args.since, args.until)
    evidence_path = ROOT / "pipeline" / "uiwang_official_2026_q3_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    independent = independent_source_evidence_check(rows, evidence)
    report["independent_official_evidence"] = independent
    report["dining_review_flags"] = classify_review_flags(rows)
    report["dining_review_flag_count"] = len(report["dining_review_flags"])
    if independent["status"] != "PASS":
        report["status"] = "HOLD"
        report["failures"] = sorted(set(report["failures"] + independent["failures"]))
    report["baseline_json_sha256"] = hashlib.sha256(baseline_bytes).hexdigest()
    if raw_path.read_bytes() != baseline_bytes:
        raise RuntimeError("raw baseline changed during read-only replay")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "candidate_rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "source": args.source, "status": report["status"],
        "selected_failed_files": report["selected_failed_files"],
        "staged_new_rows": report["staged_new_rows"],
        "failures": report["failures"],
        "audit": str(out_dir / "audit.json"),
        "candidate": str(out_dir / "candidate_rows.json"),
        "raw_unchanged": True, "publish": False,
    }, ensure_ascii=False, indent=2), flush=True)
    if args.fail_on_hold and report["status"] != "READY_FOR_REVIEW":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
