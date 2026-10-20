#!/usr/bin/env python3
"""Export an independent public transaction ledger from fully verified council files.

This viewer is not the recommendation dataset. A single QA failure excludes the
entire source; legacy rows admitted by incremental ingestion are not grandfathered
into this public, full-history ledger.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from qa_council_publication import assess

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = ("transactions.html", "transactions.js", "transactions.css")


def verified_ledger(root: Path = ROOT, generated_at: str | None = None) -> dict:
    results: list[dict] = []
    held: list[dict] = []
    verified_sources: list[dict] = []
    for path in sorted((root / "data" / "raw").glob("*_expense.json")):
        source = path.stem.removesuffix("_expense")
        discovery_path = root / "reports" / f"capital-backfill-discovery-{source}.json"
        if not discovery_path.is_file():
            continue  # Non-council feeds use different provenance/QA contracts.
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
            gate = assess(source, payload, discovery)
            if gate["status"] != "PUBLISH_READY":
                held.append({"source_key": source, "reason": gate["failures"]})
                continue

            official_posts = {p["post_url"]: p for p in discovery["posts"]
                              if p.get("source") == source and p.get("post_url")}
            source_rows = []
            for row in payload["rows"]:
                post = official_posts[row["source_post_url"]]
                # The gate checks post/file lineage. Also ensure that a displayed
                # institution is the same one as the official linked post.
                if row.get("institution") != post.get("institution"):
                    raise ValueError("institution_mismatch_with_official_post")
                source_rows.append({
                    "row_id": row["row_id"],
                    "source_key": source,
                    "institution": post["institution"],
                    "jurisdiction": post.get("jurisdiction") or "",
                    "used_date": row["used_date"],
                    "role": row.get("role") or "",
                    "merchant": row["merchant"],
                    "address": row.get("address") or "",
                    "purpose": row.get("purpose") or "",
                    "amount": row["amount"],
                    "source_post_url": row["source_post_url"],
                    "source_attachment_url": row["source_attachment_url"],
                    "source_attachment_name": row.get("source_attachment_name") or "",
                    "source_sheet": row.get("source_sheet") or "",
                    "source_row": row.get("source_row"),
                })
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError) as error:
            # Any unexpected source corruption is an explicit HOLD, never a
            # partial publication of its records.
            held.append({"source_key": source, "reason": [type(error).__name__ + ":" + str(error)[:120]]})
            continue

        source_rows.sort(key=lambda row: (row["used_date"], row["row_id"]), reverse=True)
        results.extend(source_rows)
        verified_sources.append({
            "source_key": source,
            "institution": source_rows[0]["institution"],
            "rows": len(source_rows),
            "total_amount": sum(r["amount"] for r in source_rows),
            "earliest_date": source_rows[-1]["used_date"],
            "latest_date": source_rows[0]["used_date"],
            "verified_files": gate["verified_files"],
        })

    results.sort(key=lambda row: (row["used_date"], row["row_id"]), reverse=True)
    verified_sources.sort(key=lambda row: (-row["rows"], row["institution"]))
    return {
        "schema_version": 1,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "qa_policy": "full_source_100_percent_date_amount_official_attachment",
        "scope": "공식 의회 업무추진비 공개 원자료 (외식 외 집행 포함)",
        "verified_source_count": len(verified_sources),
        "held_source_count": len(held),
        "verified_row_count": len(results),
        "verified_total_amount": sum(r["amount"] for r in results),
        "sources": verified_sources,
        "held_sources": held,
        "rows": results,
    }


def build_verified_transactions(output_dir: Path, root: Path = ROOT,
                                generated_at: str | None = None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger = verified_ledger(root, generated_at)
    if not ledger["rows"]:
        raise RuntimeError("zero fully verified council transactions: refusing an empty publication")
    (output_dir / "verified-transactions.json").write_text(
        json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    for name in PUBLIC_FILES:
        shutil.copyfile(root / "site" / name, output_dir / name)
    print(f"verified ledger: {ledger['verified_row_count']} rows from "
          f"{ledger['verified_source_count']} sources; {ledger['held_source_count']} held")
    return ledger
