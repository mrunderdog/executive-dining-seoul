import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from refresh_health import classify, from_tsv, from_incremental, report, markdown
from incremental_monthly_refresh import refresh_one


class RefreshHealthTests(unittest.TestCase):
    def test_classification_and_last_good(self):
        states = from_tsv("icheon\tSTALE_OK:DISCOVERY\nansan\tOK\nsuwon\tSTALE_OK:NO_CHANGE\nyangju\tINGEST_FAILED\n")
        value = report("full", states, now=datetime(2026, 10, 20, tzinfo=timezone.utc))
        self.assertEqual(value["status"], "DEGRADED")
        self.assertEqual(value["counts"], {"updated": 1, "no_change": 1, "stale_last_good": 1, "failed": 1})
        self.assertIn("기존 자료 유지", markdown(value))

    def test_total_failure_and_stale_health_is_not_green(self):
        for rows in (
            "icheon\\tSTALE_OK:INGEST\\nansan\\tFAILED:DISCOVERY\\n",
            "icheon\\tSTALE_OK:DISCOVERY\\n",
            "icheon\\tFAILED:INGEST\\n",
        ):
            status = report("full", from_tsv(rows))
            self.assertEqual(status["status"], "FAILED")
        partial = report("full", from_tsv("icheon\\tNO_CHANGE\\nansan\\tFAILED:INGEST\\n"))
        self.assertEqual(partial["status"], "DEGRADED")

    def test_incremental_no_change(self):
        statuses = from_incremental('{"mode":"incremental","results":[{"source":"icheon","status":"NO_CHANGE"},{"source":"ansan","status":"UPDATED"}]}')
        self.assertEqual(report("incremental", statuses)["status"], "OK")
        self.assertEqual(classify("STALE_OK:STRICT_QA"), "stale_last_good")

    def test_degraded_without_fail_and_rejects_bad_status(self):
        self.assertEqual(report("full", from_tsv("icheon\tSTALE_OK:DISCOVERY\n"))["status"], "DEGRADED")
        for bad in ("", "icheon\tOK\nicheon\tOK\n", "icheon OK"):
            with self.assertRaises(ValueError):
                from_tsv(bad)

    def test_incremental_cannot_skip_strict_qa_on_changed_rows(self):
        calls = []
        def run(cmd, timeout=180):
            calls.append(cmd)
            if any(item.endswith("qa_council_publication.py") for item in cmd):
                return False, '{"status": "HOLD", "failures": ["bad_amount"]}'
            return True, '{"source":"icheon","rows":2,"files":1}'
        with patch("incremental_monthly_refresh.run", side_effect=run), patch("incremental_monthly_refresh.restore_source") as restore:
            outcome = refresh_one("icheon", "2026-07", "2026-10")
        self.assertTrue(outcome["status"].endswith("STRICT_QA"))
        self.assertTrue(any(any(item.endswith("qa_council_publication.py") for item in cmd) for cmd in calls))
        self.assertFalse(any(any(item.endswith("build_source_candidates.py") for item in cmd) for cmd in calls))
        restore.assert_called_once_with("icheon")


if __name__ == "__main__":
    unittest.main()
