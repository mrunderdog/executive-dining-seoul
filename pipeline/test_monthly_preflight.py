"""Offline, mutation-isolated tests of next month's incremental collection semantics."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import incremental_monthly_refresh as monthly
from refresh_health import from_incremental, report


class MonthlyIncrementalPreflight(unittest.TestCase):
    def execute_synthetic_batch(self, states):
        with tempfile.TemporaryDirectory() as tmp:
            status = Path(tmp) / "incremental-council-status.json"
            sources = [SimpleNamespace(key=name) for name in states]
            def simulated(source, since, until):
                if states[source] == "WORKER_EXCEPTION":
                    raise RuntimeError("synthetic worker exception")
                return {"source": source, "status": states[source], "stages": {}}
            with (patch.object(monthly, "STATUS", status),
                  patch.object(monthly, "SOURCES", sources),
                  patch.object(monthly, "refresh_one", side_effect=simulated),
                  patch.object(monthly, "restore_source") as restored,
                  patch.object(sys, "argv", ["incremental_monthly_refresh.py"]),
                  contextlib.redirect_stdout(io.StringIO())):
                failure = False
                try:
                    monthly.main()
                except SystemExit:
                    failure = True
            payload = json.loads(status.read_text(encoding="utf-8"))
            return payload, failure, restored.call_args_list

    def test_partial_failure_keeps_successful_sources_and_reports_degraded(self):
        result, failed, restored = self.execute_synthetic_batch(
            {"icheon": "UPDATED", "ansan": "FAILED:INGEST", "suwon": "STALE_OK:DISCOVERY"})
        self.assertFalse(failed)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["stale_ok"], 1)
        self.assertEqual([x["source"] for x in result["results"]], ["icheon", "ansan", "suwon"])
        self.assertEqual(report("incremental", from_incremental(json.dumps(result)))["status"], "DEGRADED")

    def test_all_sources_stale_or_failed_exit_nonzero_without_erasing_status(self):
        result, failed, _ = self.execute_synthetic_batch(
            {"icheon": "STALE_OK:STRICT_QA", "ansan": "FAILED:DISCOVERY"})
        self.assertTrue(failed)
        self.assertEqual(report("incremental", from_incremental(json.dumps(result)))["status"], "FAILED")
        self.assertEqual(result["sources"], 2)

    def test_unhandled_worker_crash_without_baseline_is_failed_not_stale(self):
        result, failed, restored = self.execute_synthetic_batch({"new_council": "WORKER_EXCEPTION"})
        self.assertTrue(failed)
        self.assertEqual(result["results"][0]["status"], "FAILED:WORKER")
        self.assertEqual(len(restored), 1)

    def test_restore_last_good_files_and_drop_untracked_source_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            raw = folder / "data/raw/icheon_expense.json"
            candidate = folder / "reports/icheon-executive-candidates.json"
            raw.parent.mkdir(parents=True)
            candidate.parent.mkdir(parents=True)
            raw.write_bytes(b"CORRUPTED NEW RAW")
            candidate.write_bytes(b"PARTIAL NEW CANDIDATES")
            def committed_bytes(rel):
                return b"LAST-GOOD ORIGINAL RAW" if rel == "data/raw/icheon_expense.json" else None
            with (patch.object(monthly, "ROOT", folder),
                  patch.object(monthly, "git_head_bytes", side_effect=committed_bytes)):
                monthly.restore_source("icheon")
            self.assertEqual(raw.read_bytes(), b"LAST-GOOD ORIGINAL RAW")
            self.assertFalse(candidate.exists())

    def test_stage_timeout_is_failed_and_never_interpreted_as_no_change(self):
        with patch.object(monthly.subprocess, "run", side_effect=subprocess.TimeoutExpired(["python", "ingest.py"], 1)):
            ok, output = monthly.run(["python", "ingest.py"], 1)
        self.assertFalse(ok)
        self.assertIn("TIMEOUT after 1s", output)

    def test_november_scheduled_mode_and_validate_does_not_publish(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/monthly.yml").read_text(encoding="utf-8")
        self.assertIn("0 3 15 2,3,5,6,8,9,11,12 *", workflow)
        self.assertIn('MODE="incremental"', workflow)
        self.assertIn('[[ "$MODE" != "validate" ]]', workflow)
        self.assertIn("if: steps.mode.outputs.ingest == 'true'", workflow)
        self.assertIn("timeout-minutes: 330", workflow)
        self.assertIn("check_monthly_incremental_status.py", workflow)


if __name__ == "__main__":
    unittest.main()
