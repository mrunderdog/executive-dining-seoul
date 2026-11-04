#!/usr/bin/env python3
"""Read-only, period-scoped live audit for five P1 council sources.

Executes discovery, incremental ingestion, strict QA and lossless data integrity
in an ephemeral CI checkout. Never commits or publishes source data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from capital_backfill import SOURCES, canonical_attachment_url
from guard_full_council import check_integrity
from qa_council_publication import assess_incremental, git_json

TARGETS = {"anseong", "gunpo", "michuhol", "uiwang", "incheon_council"}
REPORTS = ROOT / "reports" / "recovery" / "p1-five-councils"


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def run_stage(cmd: list[str], seconds: int, log_name: str) -> dict:
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           timeout=seconds, errors="replace")
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        rc = p.returncode
    except subprocess.TimeoutExpired as e:
        raw = e.stdout or b""
        out = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        out += f"\nTIMEOUT after {seconds} seconds"
        rc = 124
    except OSError as e:
        out, rc = repr(e), 125
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / log_name).write_text(out, encoding="utf-8")
    return {"rc": rc, "tail": out[-1400:], "log": log_name}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=sorted(TARGETS))
    ap.add_argument("--since", default="2026-07")
    ap.add_argument("--until", default="2026-10")
    args = ap.parse_args()
    source = args.source
    assert next(x for x in SOURCES if x.key == source)

    raw_path = ROOT / f"data/raw/{source}_expense.json"
    discovery_path = ROOT / f"reports/capital-backfill-discovery-{source}.json"
    prior = load(raw_path)
    before = {"raw": digest(raw_path), "discovery": digest(discovery_path)}
    old_rows = len(prior.get("rows") or [])
    old_files = len(prior.get("files") or [])
    record = {
        "source": source, "period": {"since": args.since, "until": args.until},
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_rows": old_rows, "baseline_files": old_files,
        "stages": {}, "publication": "NOT_PERFORMED",
        "site_scores_modified": False,
    }

    def hold(stage: str, info: dict):
        record["failed_stage"] = stage
        record["status"] = "STALE_OK:" + stage if old_rows else "HOLD:" + stage
        record["failed_detail"] = info

    try:
        disc = run_stage(
            [sys.executable, "pipeline/capital_backfill.py", "--source", source,
             "--since", args.since, "--until", args.until],
            320, f"{source}-discovery.log")
        record["stages"]["DISCOVERY"] = disc
        if disc["rc"] != 0:
            hold("DISCOVERY", {"log_tail": disc["tail"]})
        else:
            d = load(discovery_path)
            posts = [p for p in d.get("posts", []) if p.get("source") == source and p.get("post_url")]
            attachments = [a for p in posts for a in p.get("attachments", [])
                           if canonical_attachment_url(a.get("url"))]
            errors = [p.get("error") for p in d.get("posts", []) if p.get("error")]
            record["discovered"] = {"posts": len(posts), "downloadable_files": len(attachments),
                                    "errors": errors[:5]}
            if errors or not posts or not attachments or any(not p.get("attachments") for p in posts):
                hold("DISCOVERY", record["discovered"])
            else:
                ingest = run_stage(
                    [sys.executable, "pipeline/ingest_council_expense.py",
                     "--source", source, "--incremental"],
                    540 if source == "incheon_council" else 360,
                    f"{source}-ingest.log")
                record["stages"]["INGEST"] = ingest
                if ingest["rc"] != 0:
                    hold("INGEST", {"log_tail": ingest["tail"]})
                else:
                    if source == "uiwang":
                        reparse = run_stage(
                            [sys.executable, "pipeline/reparse_verified_uiwang_pdfs.py"],
                            360, "uiwang-verified-reparse.log")
                        record["stages"]["VERIFIED_REPARSE"] = reparse
                        if reparse["rc"] != 0:
                            hold("VERIFIED_REPARSE", {"log_tail": reparse["tail"]})
                            return
                    current = load(raw_path)
                    record["ingested"] = {
                        "rows": len(current.get("rows") or []),
                        "files": len(current.get("files") or []),
                        "errors": len(current.get("errors") or []),
                        "new_files": current.get("new_files"),
                    }
                    # Existing source QA rules, without relaxing them or
                    # automatic date corrections. Inspect provenance even when
                    # QA holds so missing/changed historical entries are visible.
                    qa = assess_incremental(
                        source, current, d,
                        git_json("HEAD", f"data/raw/{source}_expense.json"),
                        git_json("HEAD", f"reports/capital-backfill-discovery-{source}.json"))
                    record["stages"]["STRICT_QA"] = qa
                    integrity = check_integrity(source, current, prior if prior else None)
                    record["stages"]["DATA_INTEGRITY"] = integrity
                    if qa["status"] not in ("PUBLISH_READY", "NO_CHANGE"):
                        # bad_examples is intentionally truncated by the QA
                        # summary. Re-evaluate all changed/invalid records
                        # against the unchanged strict row policy.
                        from qa_council_publication import period_bounds
                        from ingest_council_expense import valid_transaction_merchant
                        from datetime import date
                        baseline_rows = {r.get("row_id"): r for r in prior.get("rows", [])}
                        bad_ids = set()
                        for row in current.get("rows", []):
                            if row == baseline_rows.get(row.get("row_id")):
                                continue
                            try:
                                used = date.fromisoformat(str(row.get("used_date") or ""))
                            except ValueError:
                                used = None
                            bounds = period_bounds(row.get("source_period"))
                            invalid = (
                                not used or not bounds or not bounds[0] <= used <= bounds[1]
                                or not valid_transaction_merchant(row.get("merchant"))
                                or isinstance(row.get("amount"), bool)
                                or not isinstance(row.get("amount"), (int, float))
                                or not 0 < row["amount"] < 50_000_000
                            )
                            if invalid:
                                bad_ids.add(str(row.get("row_id")))
                        bad_ids.update(str(e.get("row_id")) for e in qa.get("bad_examples", []))
                        record["qa_forensics"] = {
                            "invalid_rows": [
                                {k: row.get(k) for k in (
                                    "row_id", "source_post_url",
                                    "source_attachment_url", "source_attachment_name",
                                    "source_sheet", "source_row", "used_date", "merchant",
                                    "amount", "purpose", "source_period")}
                                for row in current.get("rows", [])
                                if str(row.get("row_id")) in bad_ids
                            ],
                            "ingestion_errors": current.get("errors") or [],
                            "zero_row_files": [
                                {"name": f.get("name"), "url": f.get("url"),
                                 "sha256": f.get("sha256"),
                                 "sheets": f.get("sheets", [])[:4]}
                                for f in current.get("files", [])
                                if not any(
                                    str(x.get("source_attachment_url")) == str(f.get("url"))
                                    for x in current.get("rows", [])
                                )
                            ],
                        }
                        if source == "incheon_council":
                            from incheon_source_capture import match_invalid_rows
                            capture_path = ROOT / "reports/recovery/incheon-source-capture.json"
                            capture = load(capture_path)
                            record["qa_forensics"]["original_source_capture"] = (
                                match_invalid_rows(capture, bad_ids)
                                if capture else {
                                    "invalid_row_ids": sorted(bad_ids),
                                    "missing_capture_file": True,
                                    "reason": "source capture was not produced; do not infer evidence",
                                }
                            )
                        hold("STRICT_QA", {"failures": qa.get("failures", []),
                                            "bad_examples": qa.get("bad_examples", [])})
                    elif integrity["status"] != "PASS":
                        hold("DATA_INTEGRITY", {"failures": integrity.get("failures", []),
                                                "examples": integrity.get("examples", {})})
                    else:
                        record["status"] = "NO_CHANGE" if qa["status"] == "NO_CHANGE" else "PUBLISH_READY"
    except Exception as e:
        hold("AUDIT_EXCEPTION", {"exception": repr(e)})
    finally:
        # CI checkout is ephemeral and no changes are pushed. For failure cases,
        # show that the working copy alone may differ from the committed baseline;
        # this is never an authorized publication.
        if source == "incheon_council":
            evidence = ROOT / "reports/recovery/incheon-source-capture.json"
            record["incheon_source_capture"] = {
                "exists": evidence.is_file(),
                "path": str(evidence.relative_to(ROOT)) if evidence.is_file() else None,
                "capture_sha256": digest(evidence) if evidence.is_file() else None,
            }
        record["ephemeral_working_copy_changed"] = {
            "raw": digest(raw_path) != before["raw"],
            "discovery": digest(discovery_path) != before["discovery"],
        }
        record["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        REPORTS.mkdir(parents=True, exist_ok=True)
        dest = REPORTS / f"{source}-result.json"
        dest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print(json.dumps({
            "source": source, "status": record["status"],
            "stage": record.get("failed_stage"),
            "discovered": record.get("discovered"),
            "ingested": record.get("ingested"),
            "qa": record["stages"].get("STRICT_QA"),
            "integrity": record["stages"].get("DATA_INTEGRITY"),
            "report": str(dest), "publication": "NOT_PERFORMED",
        }, ensure_ascii=False, indent=2), flush=True)
    # CI diagnostic outcome is in JSON, not the job conclusion.
    # HOLD is expected at public-origin level and must never pass as publishable.


if __name__ == "__main__":
    main()
