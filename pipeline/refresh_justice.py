#!/usr/bin/env python3
"""Rerunnable justice refresh with last-good protection.

The refresh is intentionally conservative:
- incremental runs only fetch/parse new official attachments;
- full runs reconcile current official sources and refresh the historical
  prosecution archive;
- any remote/parser/validation degradation restores the committed last-good
  dataset instead of publishing an empty or materially smaller replacement;
- validate mode is completely offline and is suitable for CI.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "reports" / "justice-refresh-status.json"

JUSTICE_PATHS = [
    "data/raw/justice_leadership_expense.json",
    "reports/justice-leadership-discovery.json",
    "reports/justice-leadership-discovery.md",
    "reports/justice-leadership-ingestion.md",
    "reports/justice-leadership-candidates.json",
    "reports/justice-leadership-candidates.md",
]
JUSTICE_REQUIRED = [
    "data/raw/justice_leadership_expense.json",
    "reports/justice-leadership-candidates.json",
]
ARCHIVE_PATHS = [
    "data/raw/prosecution_archive_restaurants.json",
    "reports/prosecution-archive-candidates.json",
    "reports/prosecution-archive-candidates.md",
]
ARCHIVE_REQUIRED = [
    "data/raw/prosecution_archive_restaurants.json",
    "reports/prosecution-archive-candidates.json",
]


def run(cmd: list[str], timeout: int = 300) -> tuple[bool, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return p.returncode == 0, p.stdout[-12000:]
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        return False, f"TIMEOUT after {timeout}s\n{out[-6000:]}"


def head_bytes(path: str) -> bytes | None:
    p = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return p.stdout if p.returncode == 0 else None


def restore(paths: list[str]) -> None:
    for rel in paths:
        payload = head_bytes(rel)
        path = ROOT / rel
        if payload is None:
            if path.exists():
                path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def has_head_baseline(paths: list[str]) -> bool:
    return all(head_bytes(path) is not None for path in paths)


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def head_json(path: str) -> dict:
    payload = head_bytes(path)
    if payload is None:
        return {}
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


def last_json(text: str) -> dict:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return {}


def justice_metrics() -> dict:
    raw = load_json(JUSTICE_REQUIRED[0])
    cand = load_json(JUSTICE_REQUIRED[1])
    rows = list(raw.get("rows") or [])
    merchants = [r for r in rows if str(r.get("merchant") or "").strip()]
    return {
        "rows": len(rows),
        "merchant_rows": len(merchants),
        "eligible": int(cand.get("eligible_count") or 0),
    }


def archive_metrics() -> dict:
    raw = load_json(ARCHIVE_REQUIRED[0])
    cand = load_json(ARCHIVE_REQUIRED[1])
    return {
        "entities": int(raw.get("row_count") or len(raw.get("rows") or [])),
        "eligible": int(cand.get("eligible_count") or 0),
    }


def validate_justice() -> dict:
    metrics = justice_metrics()
    if metrics["rows"] <= 0 or metrics["merchant_rows"] <= 0:
        raise ValueError("justice dataset is empty")
    if metrics["merchant_rows"] / metrics["rows"] < 0.60:
        raise ValueError(f"merchant coverage degraded: {metrics}")
    if metrics["eligible"] <= 0:
        raise ValueError("justice candidate set is empty")

    old_raw = head_json(JUSTICE_REQUIRED[0])
    old_cand = head_json(JUSTICE_REQUIRED[1])
    old_rows = len(old_raw.get("rows") or [])
    old_eligible = int(old_cand.get("eligible_count") or 0)

    if old_rows and metrics["rows"] < max(50, int(old_rows * 0.50)):
        raise ValueError(f"justice rows degraded vs baseline: {metrics['rows']} < 50% of {old_rows}")
    if old_eligible and metrics["eligible"] < max(10, int(old_eligible * 0.40)):
        raise ValueError(
            f"justice eligible set degraded vs baseline: {metrics['eligible']} < 40% of {old_eligible}"
        )
    return metrics


def validate_archive() -> dict:
    metrics = archive_metrics()
    if metrics["entities"] < 70:
        raise ValueError(f"prosecution archive degraded below 70 entities: {metrics}")
    if metrics["eligible"] <= 0:
        raise ValueError("prosecution archive candidate set is empty")

    old = head_json(ARCHIVE_REQUIRED[0])
    old_entities = int(old.get("row_count") or len(old.get("rows") or []))
    if old_entities and metrics["entities"] < int(old_entities * 0.80):
        raise ValueError(
            f"prosecution archive degraded vs baseline: {metrics['entities']} < 80% of {old_entities}"
        )
    return metrics


def restore_justice(status: str, reason: str) -> dict:
    restore(JUSTICE_PATHS)
    if not has_head_baseline(JUSTICE_REQUIRED):
        return {"status": f"FAILED:{status}", "reason": reason, "metrics": {}}
    try:
        metrics = validate_justice()
    except Exception as exc:
        return {
            "status": "FAILED:BASELINE_INVALID",
            "reason": f"{reason}; baseline validation failed: {type(exc).__name__}: {exc}",
            "metrics": {},
        }
    return {"status": f"STALE_OK:{status}", "reason": reason, "metrics": metrics}


def restore_archive(status: str, reason: str) -> dict:
    restore(ARCHIVE_PATHS)
    if not has_head_baseline(ARCHIVE_REQUIRED):
        return {"status": f"FAILED:{status}", "reason": reason, "metrics": {}}
    try:
        metrics = validate_archive()
    except Exception as exc:
        return {
            "status": "FAILED:BASELINE_INVALID",
            "reason": f"{reason}; archive baseline validation failed: {type(exc).__name__}: {exc}",
            "metrics": {},
        }
    return {"status": f"STALE_OK:{status}", "reason": reason, "metrics": metrics}


def refresh_justice(mode: str) -> dict:
    incremental = mode == "incremental"
    discover = [sys.executable, "pipeline/justice_leadership_discovery.py"]
    ingest = [sys.executable, "pipeline/ingest_justice_leadership_expense.py"]
    if incremental:
        discover.append("--incremental")
        ingest.append("--incremental")

    ok, out = run(discover, 180)
    print(out, end="" if out.endswith("\n") else "\n")
    if not ok:
        return restore_justice("DISCOVERY", out[-2000:])

    ok, out = run(ingest, 300)
    print(out, end="" if out.endswith("\n") else "\n")
    if not ok:
        return restore_justice("INGEST", out[-2000:])

    result = last_json(out)
    ingest_status = str(result.get("status") or "")

    if ingest_status == "NO_CHANGE":
        # Discovery files carry fresh timestamps even when no source changed.
        # Restore them too so an idempotent rerun produces no repository churn.
        restore(JUSTICE_PATHS)
        try:
            metrics = validate_justice()
        except Exception as exc:
            return {
                "status": "FAILED:BASELINE_INVALID",
                "reason": f"NO_CHANGE baseline validation failed: {type(exc).__name__}: {exc}",
                "metrics": {},
            }
        return {"status": "NO_CHANGE", "reason": "", "metrics": metrics}

    if ingest_status.startswith("STALE_OK:"):
        return restore_justice(ingest_status.removeprefix("STALE_OK:"), ingest_status)

    ok, build_out = run([sys.executable, "pipeline/build_justice_leadership_candidates.py"], 60)
    print(build_out, end="" if build_out.endswith("\n") else "\n")
    if not ok:
        return restore_justice("CANDIDATE", build_out[-2000:])

    try:
        metrics = validate_justice()
    except Exception as exc:
        return restore_justice("VALIDATION", f"{type(exc).__name__}: {exc}")

    return {"status": "UPDATED", "reason": "", "metrics": metrics}


def refresh_archive(mode: str) -> dict:
    if mode == "incremental":
        if not all((ROOT / path).exists() for path in ARCHIVE_REQUIRED):
            return {"status": "SKIPPED:NO_BASELINE", "reason": "", "metrics": {}}
        try:
            return {"status": "BASELINE_OK", "reason": "", "metrics": validate_archive()}
        except Exception as exc:
            return restore_archive("VALIDATION", f"{type(exc).__name__}: {exc}")

    ok, out = run([sys.executable, "pipeline/ingest_prosecution_archive.py"], 120)
    print(out, end="" if out.endswith("\n") else "\n")
    if not ok:
        return restore_archive("ARCHIVE_FETCH", out[-2000:])
    try:
        metrics = validate_archive()
    except Exception as exc:
        return restore_archive("ARCHIVE_VALIDATION", f"{type(exc).__name__}: {exc}")
    return {"status": "UPDATED", "reason": "", "metrics": metrics}


def offline_validate() -> dict:
    return {
        "mode": "validate",
        "justice": {"status": "OK", "reason": "", "metrics": validate_justice()},
        "prosecution_archive": {
            "status": "OK",
            "reason": "",
            "metrics": validate_archive(),
        },
    }


def write_status(payload: dict) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("incremental", "full", "validate"), default="incremental")
    args = ap.parse_args()

    if args.mode == "validate":
        payload = offline_validate()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    payload = {
        "mode": args.mode,
        "justice": refresh_justice(args.mode),
        "prosecution_archive": refresh_archive(args.mode),
    }
    write_status(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    failed = [
        name
        for name in ("justice", "prosecution_archive")
        if str(payload[name].get("status") or "").startswith("FAILED:")
    ]
    if failed:
        raise SystemExit("no usable last-good baseline for: " + ", ".join(failed))


if __name__ == "__main__":
    main()
