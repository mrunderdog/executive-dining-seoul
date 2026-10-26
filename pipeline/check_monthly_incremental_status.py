#!/usr/bin/env python3
"""Assess monthly incremental source health without suppressing partial publishing."""
import argparse,json
from pathlib import Path
from refresh_health import from_incremental
from check_council_refresh_outcome import evaluate

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--status-file",type=Path,required=True)
 args=p.parse_args()
 try:
  statuses=from_incremental(args.status_file.read_text(encoding="utf-8"))
  ok,msg=evaluate(statuses)
 except (ValueError,OSError,TypeError,KeyError) as e:
  ok,msg=False,f"invalid incremental status: {e}"
 print(("::warning" if ok and "DEGRADED" in msg else "::error" if not ok else "Monthly council refresh")+f"::{msg}")
 if not ok:raise SystemExit(1)
if __name__=="__main__":main()
