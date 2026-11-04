"""Lossless, ephemeral official-source provenance capture for Incheon P1.

Never mutates public transactions or their scores. Capture is registered at
process exit so an ingestion failure or SystemExit still leaves an audit
artifact. A hard-killed process cannot guarantee an artifact; the diagnostic
runner reports that explicitly rather than fabricating evidence.
"""
from __future__ import annotations

import atexit
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def as_cell(value):
    """Keep original worksheet cell type and value; no OCR or numeric inference."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return {"type": type(value).__name__, "value": value}
    return {"type": type(value).__name__, "value": str(value)}


class OriginalSourceCapture:
    def __init__(self, source, destination):
        self.destination = Path(destination)
        self.doc = {
            "schema_version": 1,
            "source": source,
            "scope": "newly_attempted_official_attachments_only",
            "publication_authorized": False,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "files": [],
            "skipped_baseline_file_urls": [],
            "attachment_errors": [],
            "status": "RUNNING",
        }
        atexit.register(self.write)

    def skipped(self, url):
        self.doc["skipped_baseline_file_urls"].append(url)

    def start(self, post, url, name):
        entry = {
            "post_url": post.get("post_url"),
            "post_title": post.get("title"),
            "source_period": post.get("period"),
            "attachment_url": url,
            "attachment_name": name,
            "status": "FETCH_STARTED",
            "phase": "download",
            "sha256": None,
            "sheets": [],
        }
        self.doc["files"].append(entry)
        return entry

    def downloaded(self, entry, data, sha):
        entry["sha256"] = sha
        entry["bytes"] = len(data)
        entry["status"] = "DOWNLOADED"
        entry["phase"] = "parse"

    def sheet(self, entry, name, rows):
        record = {
            "sheet": name,
            "raw_rows_count": len(rows),
            "raw_source_rows": [
                {"source_row": n, "source_cells": [as_cell(c) for c in row]}
                for n, row in enumerate(rows, 1)
            ],
            "normalized_rows": [],
            "normalizer": None,
        }
        entry["sheets"].append(record)
        entry["phase"] = "normalize"
        return record

    def normalized(self, entry, record, normalized_rows, info):
        record["normalizer"] = info
        for row in normalized_rows:
            n = row.get("source_row")
            original = (
                record["raw_source_rows"][n - 1]["source_cells"]
                if isinstance(n, int) and 1 <= n <= len(record["raw_source_rows"])
                else None
            )
            record["normalized_rows"].append({
                "row_id": row.get("row_id"),
                "row": row,
                "original_source_cells": original,
                "original_row_address_verified": original is not None,
            })
        entry["status"] = "SHEET_PARSED"
        entry["phase"] = "parse"

    def succeeded(self, entry):
        entry["status"] = "PARSED"
        entry["phase"] = "complete"

    def failed(self, entry, exc):
        error = {
            "post_url": entry["post_url"],
            "attachment_url": entry["attachment_url"],
            "attachment_name": entry["attachment_name"],
            "source_period": entry["source_period"],
            "attachment_sha256": entry.get("sha256"),
            "failed_phase": entry["phase"],
            "error": f"{type(exc).__name__}: {exc}",
            "recorded_sheets": [s["sheet"] for s in entry["sheets"]],
        }
        entry["status"] = "ERROR"
        entry["failure"] = error
        self.doc["attachment_errors"].append(error)

    def write(self):
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        self.doc["status"] = (
            "COMPLETE_WITH_ERRORS" if self.doc["attachment_errors"]
            else "CAPTURE_COMPLETE"
        )
        self.doc["saved_at_utc"] = datetime.now(timezone.utc).isoformat()
        tmp = self.destination.with_name(self.destination.name + ".tmp")
        tmp.write_text(json.dumps(self.doc, ensure_ascii=False, indent=2, default=str) + "\n",
                       encoding="utf-8")
        os.replace(tmp, self.destination)


def match_invalid_rows(capture, invalid_ids):
    """Return every invalid candidate and its exact original cells.

    Missing captures remain visible as an explicit evidence defect, never
    silently replaced with inferred data.
    """
    ids = set(invalid_ids)
    candidates = {}
    for entry in capture.get("files", []):
        for sheet in entry.get("sheets", []):
            for item in sheet.get("normalized_rows", []):
                row_id = item.get("row_id")
                if row_id in ids:
                    candidates.setdefault(row_id, []).append({
                        "post_url": entry.get("post_url"),
                        "attachment_url": entry.get("attachment_url"),
                        "attachment_name": entry.get("attachment_name"),
                        "attachment_sha256": entry.get("sha256"),
                        "source_sheet": sheet.get("sheet"),
                        "source_row": item["row"].get("source_row"),
                        "original_source_cells": item.get("original_source_cells"),
                        "normalized_row": item["row"],
                        "original_row_address_verified": item.get("original_row_address_verified"),
                    })
    return {
        "invalid_row_ids": sorted(ids),
        "invalid_row_evidence": {key: candidates.get(key, []) for key in sorted(ids)},
        "invalid_row_ids_missing_original_cells": [
            key for key in sorted(ids)
            if not candidates.get(key) or any(
                not r["original_row_address_verified"] for r in candidates[key]
            )
        ],
        "attachment_errors": capture.get("attachment_errors", []),
    }
