#!/usr/bin/env python3
"""Uiwang production ranking/site diff, in a disposable filesystem overlay.

Reads verified same-run staging artifacts; never writes data/raw, reports
on the checkout, or a public Pages directory. No payee branch is established
from a name-only restaurant directory match.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
from collections import Counter
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import patch

import build_source_candidates
import build_site
import published_sources

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data/raw"
REPORTS=ROOT/"reports"
INTEGRATED=REPORTS/"recovery/uiwang-integrated"
VENUE=REPORTS/"recovery/uiwang-venue"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy_overlay(source, target, *, excluded=()):
    """Read-only links for unchanged files; only changed Uiwang files are written."""
    target.mkdir(parents=True,exist_ok=True)
    excluded=set(excluded)
    for item in source.iterdir():
        if item.name not in excluded:
            (target/item.name).symlink_to(item.resolve(),target_is_directory=item.is_dir())


def checked_candidate_rows(baseline, staged, decisions, all_transactions):
    """Keep 218 financial records in scratch; only 84 score-qualified."""
    if (len(staged),len(decisions),len(all_transactions))!=(193,193,218):
        raise ValueError("expected 193/193/218 independent source coverage")
    screened={d["row_id"]:d for d in decisions}
    candidates={r["row_id"]:r for r in staged}
    if len(screened)!=193 or len(candidates)!=193 or set(screened)!=set(candidates):
        raise ValueError("inconsistent screening or duplicate IDs")
    existing={r["row_id"] for r in baseline["rows"]}
    full, eligible=[],set()
    for original in all_transactions:
        row=copy.deepcopy(original)
        rid=row.get("row_id")
        period=row.get("source_period")
        try:
            when=date.fromisoformat(str(row["used_date"]))
        except (ValueError,TypeError,KeyError):
            raise ValueError("invalid official source date") from None
        if (rid in existing or not rid or len(period or [])!=3
            or [when.year,when.month]!=period[:2]):
            raise ValueError("date/identity outside source")
        if rid in candidates and candidates[rid]!=original:
            raise ValueError("financial row differs from candidate source")
        if rid in screened:
            d=screened[rid]
            if (d["merchant"]!=row["merchant"] or d["source_date"]!=row["used_date"]
                or d["amount_krw"]!=row["amount"]):
                raise ValueError("screening evidence mismatch")
            if d.get("score_eligible") is True:
                eligible.add(rid)
        row["date_quality"]="in_period"  # in scratch overlay ONLY
        full.append(row)
    if len({r["row_id"] for r in full})!=218 or len(eligible)!=84:
        raise ValueError("wrong financial row/eligible role count")
    if not set(candidates).issubset({r["row_id"] for r in full}):
        raise ValueError("missing original rows")
    return full,eligible


def serialize_record(row):
    # Stable snapshot for verifying that unrelated source output is retained.
    return json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(",",":"))


@contextmanager
def override_paths(staged_raw, staged_reports):
    with patch.object(build_source_candidates,"RAW",staged_raw), \
         patch.object(published_sources,"RAW_DIR",staged_raw), \
         patch.object(published_sources,"REPORTS",staged_reports):
        yield


def render_site(output):
    before=list(sys.argv)
    try:
        sys.argv=["build_site.py","--output",str(output)]
        build_site.main()
    finally:
        sys.argv=before
    html=output.read_text(encoding="utf-8")
    if ("__DATA__" in html or "__STATS__" in html or "__ORIGINS__" in html
        or "__STORY__" in html or len(html)<200_000):
        raise ValueError("site HTML build is missing expected dataset/runtime")
    return load(output.with_name("build-meta.json"))


def one_snapshot(raw_doc, staged_raw, staged_reports, output_path, *, eligible_ids=None, baseline_ids=None):
    (staged_raw/"uiwang_expense.json").write_text(
        json.dumps(raw_doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    original_meal = build_source_candidates.looks_meal
    original_plausible = published_sources._plausible_transaction
    def permitted(row, original):
        rid=row.get("row_id")
        if eligible_ids is not None and rid not in baseline_ids and rid not in eligible_ids:
            return False
        return original(row)
    with override_paths(staged_raw,staged_reports), \
         patch.object(build_source_candidates,"looks_meal",
                      lambda row: permitted(row,original_meal)), \
         patch.object(published_sources,"_plausible_transaction",
                      lambda row: permitted(row,original_plausible)):
        source_rows, candidates=build_source_candidates.build_candidates("uiwang")
        (staged_reports/"uiwang-executive-candidates.json").write_text(
            json.dumps({"source":"uiwang","candidate_count":len(candidates),
                        "candidates":candidates},ensure_ascii=False,indent=2)+"\n",
            encoding="utf-8")
        published=published_sources._build_source_records("uiwang",
                                                         published_sources.SOURCE_SPECS["uiwang"])
        payload=build_site.apply_evidence_semantics(
            build_site.merge_global_entities(
                build_site.merge_extra_published(
                    build_site.merge_published_sources(build_site.load_payload()))))
        meta=render_site(output_path)
    # App-level entity merging can join an Uiwang establishment with another
    # source. Keep the full dataset hash, source-specific recommendations, and
    # other records' counts in the audit for independent review.
    visible=payload.get("records") or []
    return {
        "ranking_input_transactions":len(source_rows),
        "source_candidate_count":len(candidates),
        "source_rank_preview":candidates[:15],
        "published_source_record_count":len(published),
        "published_source_records":[{"name":x.get("name"),
                                     "rank":(x.get("executive") or {}).get("rank"),
                                     "score":(x.get("executive") or {}).get("score"),
                                     "visits":(x.get("evidence") or {}).get("visits"),
                                     "spend":(x.get("evidence") or {}).get("spend"),
                                     "payment_branch_verified":x.get("payment_branch_verified"),
                                     "location":x.get("address")}
                                    for x in published],
        "site":meta,
        "site_record_count":len(visible),
        "non_uiwang_signatures":Counter(
            serialize_record(r) for r in visible
            if r.get("origin")!="의왕시"
        ),
        "page_sha256":digest(output_path),
        "site_output_bytes":output_path.stat().st_size,
    }


def simulate(baseline,screened,integrated,venue):
    if integrated.get("status")!="READY_FOR_RELEASE_REVIEW":
        raise ValueError("integrated strict QA has not passed")
    if venue.get("source_validation")!="PASS" or venue.get("release_decision")!="HOLD_IDENTITY_AND_RANKING":
        raise ValueError("unapproved screening or source coverage")
    original=copy.deepcopy(baseline)
    all_new,eligible_ids=checked_candidate_rows(
        baseline,screened["rows"],screened["decisions"],screened["financial_rows"])
    baseline_ids={r.get("row_id") for r in baseline["rows"]}
    proposed={**copy.deepcopy(baseline),
              "rows":[*copy.deepcopy(baseline["rows"]),*all_new]}
    if baseline!=original:
        raise AssertionError("historical rows changed while staging")
    with tempfile.TemporaryDirectory(prefix="uiwang-site-dryrun-") as workdir:
        work=Path(workdir)
        stage_raw=work/"raw"
        stage_reports=work/"reports"
        copy_overlay(RAW,stage_raw,excluded=("uiwang_expense.json",))
        copy_overlay(REPORTS,stage_reports,excluded=("uiwang-executive-candidates.json",))
        base=one_snapshot(baseline,stage_raw,stage_reports,work/"baseline.html")
        repeat_base=one_snapshot(baseline,stage_raw,stage_reports,work/"repeated_baseline.html")
        revised=one_snapshot(proposed,stage_raw,stage_reports,work/"proposed.html",
                             eligible_ids=eligible_ids,baseline_ids=baseline_ids)
    new_other = revised["non_uiwang_signatures"] - base["non_uiwang_signatures"]
    removed_other = base["non_uiwang_signatures"] - revised["non_uiwang_signatures"]
    failures=[]
    baseline_repeat_drift=base["non_uiwang_signatures"]!=repeat_base["non_uiwang_signatures"]
    if baseline_repeat_drift:
        failures.append("baseline_site_is_not_repeatable_within_process")
    if removed_other:
        failures.append("existing_non_uiwang_site_records_changed_or_removed")
    if base["published_source_record_count"] > revised["published_source_record_count"]:
        failures.append("uiwang_published_record_count_decreased")
    if revised["published_source_record_count"] > 0 and any(
        x["payment_branch_verified"] for x in revised["published_source_records"]):
        failures.append("unsupported_payment_branch_verification")
    if len(all_new)!=218 or len(eligible_ids)!=84 or baseline!=original:
        failures.append("baseline_or_eligible_row_mismatch")
    return {
        "status":"PREVIEW_PASS" if not failures else "HOLD",
        "baseline_repeat_site_record_count":repeat_base["site_record_count"],
        "baseline_repeat_non_uiwang_changed_count":sum(
            (base["non_uiwang_signatures"]-repeat_base["non_uiwang_signatures"]).values()),
        "baseline_repeat_site_sha256":repeat_base["page_sha256"],
        "other_origin_removed_samples":[{
            "origin":json.loads(key).get("origin"),
            "name":json.loads(key).get("name"),
            "entity_id":json.loads(key).get("entity_id"),
            "count":count,
        } for key,count in (removed_other).most_common(12)],
        "baseline_raw_rows":len(baseline["rows"]),
        "new_scoring_input_rows":len(eligible_ids),
        "new_financial_rows_staged":len(all_new),
        "full_source_staged_rows":integrated["total_staged_rows"],
        "financial_source_staged_files":integrated["total_staged_files"],
        "baseline":{"ranking_input_rows":base["ranking_input_transactions"],
                    "ranked_source_names":base["source_candidate_count"],
                    "published_source_records":base["published_source_records"],
                    "site_record_count":base["site_record_count"],
                    "site_output_bytes":base["site_output_bytes"],
                    "page_sha256":base["page_sha256"]},
        "proposed":{"ranking_input_rows":revised["ranking_input_transactions"],
                    "ranked_source_names":revised["source_candidate_count"],
                    "published_source_records":revised["published_source_records"],
                    "site_record_count":revised["site_record_count"],
                    "site_output_bytes":revised["site_output_bytes"],
                    "page_sha256":revised["page_sha256"]},
        "other_origin_records_changed":sum(removed_other.values()),
        "other_origin_records_added":sum(new_other.values()),
        "entity_identity_note":"Only verified source row IDs staged; restaurant address directory is NOT proof of card merchant branch.",
        "publication_decision":"NO_GO_PENDING_PAYMENT_BRANCH_IDENTITY",
        "failures":failures,
        "publish":False,
    }


def main():
    baseline_path=RAW/"uiwang_expense.json"
    bytes_before=baseline_path.read_bytes()
    report=simulate(
        json.loads(bytes_before),
        {"rows":load(INTEGRATED/"recommendation_candidates.json"),
         "decisions":load(VENUE/"transaction_screening.json"),
         "financial_rows":[
             *load(REPORTS/"recovery/uiwang-replay/candidate_rows.json"),
             *load(REPORTS/"recovery/uiwang-october/candidate_rows.json")]},
        load(INTEGRATED/"audit.json"),
        load(VENUE/"audit.json"))
    if baseline_path.read_bytes()!=bytes_before:
        raise RuntimeError("immutable source file changed during site preflight")
    out=ROOT/"reports/recovery/uiwang-site-dryrun"
    out.mkdir(parents=True,exist_ok=True)
    (out/"audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in (
        "status","baseline_raw_rows","new_scoring_input_rows",
        "full_source_staged_rows","other_origin_records_changed",
        "publication_decision","failures","publish")},ensure_ascii=False),flush=True)
    if report["status"]!="PREVIEW_PASS":
        raise SystemExit(2)


if __name__=="__main__":
    main()
