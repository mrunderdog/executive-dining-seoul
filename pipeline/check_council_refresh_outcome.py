#!/usr/bin/env python3
"""Set an honest GitHub Actions conclusion after the council publication steps.

This never changes the strict QA gate or public raw data. A targeted run must
succeed for its *requested* source. Full batches may publish valid sources
while reporting partial failures, but cannot pass if every source is degraded.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from refresh_health import from_tsv


def evaluate(statuses: list[dict], requested_source: str = "") -> tuple[bool, str]:
    if requested_source:
        if len(statuses) != 1 or statuses[0]["source"] != requested_source:
            return False, f"requested source {requested_source!r} did not produce exactly one status"
        row = statuses[0]
        if row["class"] not in {"updated", "no_change"}:
            return False, f"{requested_source}: {row['status']} (new data not published; last-good retained)"
        return True, f"{requested_source}: {row['status']} (source refresh healthy)"

    counts = {key: sum(r["class"] == key for r in statuses)
              for key in ("updated", "no_change", "stale_last_good", "failed")}
    healthy = counts["updated"] + counts["no_change"]
    degraded = counts["stale_last_good"] + counts["failed"]
    if not healthy:
        return False, f"full batch: no healthy sources; {degraded} failed/stale"
    if degraded:
        return True, (f"full batch DEGRADED: {healthy} healthy; {degraded} "
                      "failed/stale. Successful sources may publish; see health report.")
    return True, f"full batch OK: {healthy} healthy sources"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status-file", type=Path, required=True)
    ap.add_argument("--source", default="", help="single source selected by workflow_dispatch")
    args = ap.parse_args()
    try:
        statuses = from_tsv(args.status_file.read_text(encoding="utf-8"))
        good, message = evaluate(statuses, args.source)
    except (OSError, ValueError) as exc:
        good, message = False, f"missing/invalid refresh status: {exc}"
    if good:
        print(message)
        if "DEGRADED" in message:
            print(f"::warning title=Council refresh degraded::{message}")
    else:
        print(f"::error title=Council refresh failed::{message}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
