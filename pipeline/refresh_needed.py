#!/usr/bin/env python3
"""Conservatively skip expensive derived-data jobs when their inputs are unchanged.

The latest commit touching an output file is the watermark. Compare that commit
with current checked-out HEAD across *all* declared source paths. Do not use
timestamps: GitHub Actions GITHUB_TOKEN writes often do not emit push events.

Failures to inspect history are fail-open (recompute). Explicit manual dispatch
is always allowed to force a refresh.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False
    )


def needs_refresh(root: Path, output: str, inputs: list[str], force: bool = False) -> tuple[bool, str]:
    if force:
        return True, "explicit manual refresh"
    if not inputs:
        return True, "missing dependency declaration"
    if not (root / output).is_file():
        return True, "published output missing"
    head = _git(root, "rev-parse", "--verify", "HEAD")
    last = _git(root, "log", "-1", "--format=%H", "--", output)
    if head.returncode or last.returncode or not last.stdout.strip():
        return True, "missing or unreadable Git history"
    anchor = last.stdout.strip()
    ancestor = _git(root, "merge-base", "--is-ancestor", anchor, "HEAD")
    if ancestor.returncode:
        return True, "output watermark not an ancestor of HEAD"
    diff = _git(root, "diff", "--quiet", anchor, "HEAD", "--", *inputs)
    if diff.returncode == 0:
        return False, f"no tracked dependency changes since output commit {anchor[:12]}"
    if diff.returncode == 1:
        return True, f"input dependencies changed since output commit {anchor[:12]}"
    return True, "unable to diff dependencies; fail-open"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Committed output to use as a Git watermark")
    parser.add_argument("--input", action="append", default=[], dest="inputs",
                        help="Git pathspec for one input dependency (repeatable)")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    refresh, reason = needs_refresh(args.repo, args.output, args.inputs, args.force)
    print(f"refresh preflight: {args.output}: {reason}", file=sys.stderr)
    print("needs_refresh=" + ("true" if refresh else "false"))


if __name__ == "__main__":
    main()
