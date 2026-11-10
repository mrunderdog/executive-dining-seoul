#!/usr/bin/env python3
"""Prepare release artifact for Uiwang verified financial rows WITHOUT ranking.

This NEVER writes tracked data/raw or site files. Outputs are a reviewable
source-only release package; a separate change/approval is required to commit.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

from audit_uiwang_integrated import verify_integrated
from capital_backfill import canonical_attachment_url
from guard_full_council import check_integrity
from qa_council_publication import assess_incremental

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "reports/recovery"
RELEASE = STAGING / "uiwang-source-release"


def read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def write_json(p, content):
    Path(p).write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")


def normalize_release_rows(old, q3, oct_rows):
    baseline_ids = {r.get("row_id") for r in old}
    if len(baseline_ids) != len(old) or not baseline_ids:
        raise ValueError("invalid legacy source row keys")
    all_ids = set(baseline_ids)
    added = []
    for item in [*q3, *oct_rows]:
        raw = dict(item)
        rid = raw.get("row_id")
        period = raw.get("source_period")
        try:
            observed = date.fromisoformat(str(raw.get("used_date") or ""))
        except (ValueError, TypeError):
            raise ValueError("invalid recovered date") from None
        if (rid in all_ids or not rid or raw.get("source_key") != "uiwang"
            or not isinstance(period, list) or len(period) != 3
            or period[:2] != [observed.year, observed.month]):
            raise ValueError("duplicate, mismatched or invalid recovered source")
        if raw.get("date_quality") not in (None, "in_period"):
            raise ValueError("conflicting derived date quality")
        raw["date_quality"] = "in_period"
        all_ids.add(rid)
        added.append(raw)
    if len(q3) != 144 or len(oct_rows) != 74 or len(added) != 218:
        raise ValueError("incomplete verified 7-10 month source")
    return added


def prepare(baseline, discovery, q3, october, q3_audit, october_audit,
            integrated, october_evidence, q3_policy, october_policy, current_candidates):
    failures = []
    checked, recommendations = verify_integrated(
        baseline, discovery, q3, october, q3_audit, october_audit,
        october_evidence, q3_policy, october_policy)
    if checked.get("status") != "READY_FOR_RELEASE_REVIEW" or integrated.get("status") != checked.get("status"):
        failures.append("source_integrity_audit_not_ready")
    if len(recommendations) != 193:
        failures.append("pending_dining_candidates_coverage_incorrect")
    if current_candidates.get("source") != "uiwang" or current_candidates.get("candidate_count") != 0:
        failures.append("live_candidate_baseline_not_zero")
    new_rows = normalize_release_rows(baseline.get("rows") or [], q3, october)
    file_info = []
    official_items = october_evidence["items"]
    for expected in official_items:
        ref = canonical_attachment_url(expected["url"])
        replayed = [entry for entry in october_audit.get("file_results", [])
                    if canonical_attachment_url(entry.get("url")) == ref]
        if len(replayed) != 1:
            failures.append("missing_or_duplicate_official_october_file")
            continue
        item = replayed[0]
        if (not item.get("sha256") or not item.get("bytes")
            or item.get("parsed_count") != expected["official_transaction_count"]
            or item.get("parsed_total_krw") != expected["official_total_krw"]):
            failures.append("official_october_attachment_reconciliation_mismatch")
            continue
        file_info.append({
            "url": expected["url"], "name": expected["name"],
            "title": "2026년 10월 업무추진비 사용내역 공개",
            "sha256": item["sha256"], "bytes": item["bytes"],
            "sheets": [
                {"sheet": page["sheet"], "status": page["status"],
                 "parsed_rows": page["parsed_rows"],
                 "unparsed_transaction_like_rows": page.get("unparsed_transaction_like_rows", 0)}
                for page in item.get("pages", [])
            ]
        })
    if len(file_info) != 2:
        failures.append("missing_october_file_metadata")
    proposed = {
        **baseline,
        "rows": [*(baseline.get("rows") or []), *new_rows],
        "files": [*(baseline.get("files") or []), *file_info],
    }
    post = {
        "source": "uiwang",
        "region": "경기", "jurisdiction": "의왕시", "institution": "의왕시의회",
        "title": "2026년 10월 업무추진비 사용내역 공개",
        "post_url": october_evidence["official_post"],
        "period": [2026, 10, None],
        "attachments": [{"url": x["url"], "text": x["name"]} for x in official_items],
    }
    prior_posts = discovery.get("posts") or []
    if any(p.get("post_url") == post["post_url"] for p in prior_posts):
        failures.append("official_october_discovery_already_exists")
    updated_discovery = {**discovery, "posts": [*prior_posts, post]}
    integrity = check_integrity("uiwang", proposed, baseline)
    if integrity["status"] != "PASS":
        failures.extend(integrity["failures"])
    qa = assess_incremental("uiwang", proposed, updated_discovery, baseline, discovery)
    if qa["status"] != "PUBLISH_READY":
        failures.extend(qa["failures"] or ["source_qa_hold"])
    if len(proposed["rows"]) != 303 or len(proposed["files"]) != 35:
        failures.append("source_release_size_mismatch")
    if proposed["rows"][:len(baseline["rows"])] != baseline["rows"]:
        failures.append("legacy_transaction_mutation")
    if proposed["files"][:len(baseline["files"])] != baseline["files"]:
        failures.append("legacy_source_file_mutation")
    if current_candidates.get("candidates"):
        failures.append("nonempty_live_recommendations_not_allowed")
    report = {
        "status": "SOURCE_RELEASE_READY" if not failures else "HOLD",
        "mode": "FINANCIAL_SOURCE_ONLY",
        "current_rows": len(baseline.get("rows") or []),
        "new_rows": len(new_rows),
        "proposed_rows": len(proposed["rows"]),
        "old_files": len(baseline.get("files") or []),
        "proposed_files": len(proposed["files"]),
        "strict_qa": qa["status"],
        "integrity": integrity["status"],
        "new_recommendation_publications": 0,
        "payment_branch_verified_new": 0,
        "publish": False,
        "failures": sorted(set(failures)),
        "manual_steps": [
            "Review source ledger diff against independent audit and site zero-drift regression",
            "Commit only source/discovery release files in a separate reviewed PR",
            "Keep candidate ranking unchanged until payment identity review",
            "Confirm deployed build identity and source QA after merge",
        ],
    }
    return proposed, updated_discovery, report


def main():
    raw_path = ROOT / "data/raw/uiwang_expense.json"
    raw_bytes_before = raw_path.read_bytes()
    baseline = json.loads(raw_bytes_before)
    discovery = read_json(ROOT / "reports/capital-backfill-discovery-uiwang.json")
    q3 = read_json(STAGING / "uiwang-replay/candidate_rows.json")
    october = read_json(STAGING / "uiwang-october/candidate_rows.json")
    proposed, updated_discovery, report = prepare(
        baseline, discovery, q3, october,
        read_json(STAGING / "uiwang-replay/audit.json"),
        read_json(STAGING / "uiwang-october/audit.json"),
        read_json(STAGING / "uiwang-integrated/audit.json"),
        read_json(ROOT / "pipeline/uiwang_official_2026_10_evidence.json"),
        read_json(ROOT / "pipeline/uiwang_2026_q3_dining_dispositions.json"),
        read_json(ROOT / "pipeline/uiwang_2026_10_dining_dispositions.json"),
        read_json(ROOT / "reports/uiwang-executive-candidates.json"),
    )
    if raw_path.read_bytes() != raw_bytes_before:
        raise RuntimeError("source original changed during release preparation")
    RELEASE.mkdir(parents=True, exist_ok=True)
    write_json(RELEASE / "uiwang_expense.json", proposed)
    write_json(RELEASE / "capital-backfill-discovery-uiwang.json", updated_discovery)
    report["original_raw_sha256"] = hashlib.sha256(raw_bytes_before).hexdigest()
    report["proposed_raw_sha256"] = hashlib.sha256((RELEASE / "uiwang_expense.json").read_bytes()).hexdigest()
    write_json(RELEASE / "release_manifest.json", report)
    print(json.dumps({
        "status": report["status"], "source_rows": report["proposed_rows"],
        "source_files": report["proposed_files"],
        "new_recommendation_publications": report["new_recommendation_publications"],
        "failures": report["failures"], "publish": False,
    }, ensure_ascii=False), flush=True)
    if report["status"] != "SOURCE_RELEASE_READY":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
