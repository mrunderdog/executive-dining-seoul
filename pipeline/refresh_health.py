#!/usr/bin/env python3
"""Summarize council collection/publishing health without exposing a new site page.

The report describes the attempted refresh, not an assertion that every source
was recently published. A degraded run keeps last-good public data and raises
an Actions warning so silent partial failures are visible to operators.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "refresh-health.json"
VALID_KEY = re.compile(r"^[a-z][a-z0-9_]*$")


def classify(state: str) -> str:
    if state in {"OK", "UPDATED"}:
        return "updated"
    if state == "NO_CHANGE" or state == "STALE_OK:NO_CHANGE":
        return "no_change"
    if state.startswith("STALE_OK:"):
        return "stale_last_good"
    return "failed"


def from_tsv(text: str) -> list[dict]:
    out = []
    seen = set()
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2 or not VALID_KEY.fullmatch(parts[0]) or not parts[1].strip():
            raise ValueError(f"malformed council status row: {line[:100]!r}")
        name, state = parts[0], parts[1].strip()
        if name in seen:
            raise ValueError(f"duplicate source: {name}")
        seen.add(name)
        out.append({"source": name, "status": state, "class": classify(state)})
    if not out:
        raise ValueError("no council source statuses")
    return out


def from_incremental(text: str) -> list[dict]:
    data = json.loads(text)
    if data.get("mode") != "incremental":
        raise ValueError("not an incremental council status report")
    rows = data.get("results") or []
    if not rows:
        raise ValueError("no incremental council source statuses")
    out = []
    seen = set()
    for row in rows:
        source = row.get("source", "")
        state = row.get("status", "")
        if not VALID_KEY.fullmatch(source) or not isinstance(state, str) or not state or source in seen:
            raise ValueError(f"invalid incremental council status: {source!r}")
        seen.add(source)
        out.append({"source": source, "status": state, "class": classify(state)})
    return out


def report(mode: str, statuses: list[dict], now: datetime | None = None, url: str = "") -> dict:
    counts = Counter(row["class"] for row in statuses)
    healthy = counts["updated"] + counts["no_change"]
    problematic = counts["stale_last_good"] + counts["failed"]
    state = ("FAILED" if not healthy else
             "DEGRADED" if problematic else "OK")
    return {
        "generated_at_utc": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "status": state,
        "source_count": len(statuses),
        "counts": {key: counts[key] for key in ("updated", "no_change", "stale_last_good", "failed")},
        "workflow_run_url": url,
        "sources": statuses,
        "publication_policy": "Only strict-QA-approved new records; failed sources retain last-good and are not published.",
    }


def markdown(payload: dict) -> str:
    lines = ["## 공식 기관 수집 상태", "",
             f"- 실행 방식: `{payload['mode']}`", f"- 수집 건강도: **{payload['status']}**",
             f"- 전체 {payload['source_count']}개 · 신규 반영 {payload['counts']['updated']}개 · "
             f"변경 없음 {payload['counts']['no_change']}개 · 기존 자료 유지 {payload['counts']['stale_last_good']}개 · "
             f"사용 가능 기준자료 없음 {payload['counts']['failed']}개", "",
             "| 기관 키 | 결과 | 공개 처리 |", "|---|---|---|"]
    for row in payload["sources"]:
        action = ("QA 승인된 변경만 게시" if row["class"] == "updated" else
                  "변경 없음" if row["class"] == "no_change" else
                  "기존 자료 유지, 신규 수집 보류" if row["class"] == "stale_last_good" else
                  "신규 수집·게시 보류")
        lines.append(f"| `{row['source']}` | `{row['status']}` | {action} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--full-status", type=Path)
    group.add_argument("--incremental-status", type=Path)
    ap.add_argument("--output", type=Path, default=OUTPUT)
    args = ap.parse_args()
    if args.full_status:
        mode = "full"
        statuses = from_tsv(args.full_status.read_text(encoding="utf-8"))
    else:
        mode = "incremental"
        statuses = from_incremental(args.incremental_status.read_text(encoding="utf-8"))

    repo, run_id = os.getenv("GITHUB_REPOSITORY", ""), os.getenv("GITHUB_RUN_ID", "")
    url = f"https://github.com/{repo}/actions/runs/{run_id}" if repo and run_id else ""
    payload = report(mode, statuses, url=url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(markdown(payload))
    if payload["status"] != "OK":
        affected = ", ".join(x["source"] for x in statuses if x["class"] in {"failed", "stale_last_good"})
        print(f"::warning title=공식 기관 수집 지연::신규 게시 보류: {affected}")
    print(json.dumps({k: v for k, v in payload.items() if k != "sources"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
