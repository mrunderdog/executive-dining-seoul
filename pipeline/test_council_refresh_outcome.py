import unittest
from check_council_refresh_outcome import evaluate
from refresh_health import from_tsv

class CouncilWorkflowConclusionTests(unittest.TestCase):
    def test_target_failure_or_last_good_does_not_look_successful(self):
        for value in ("INGEST_FAILED", "STALE_OK:STRICT_QA", "STALE_OK:DISCOVERY", "VALIDATION_FAILED"):
            good, _ = evaluate(from_tsv(f"icheon\t{value}\n"), "icheon")
            self.assertFalse(good, value)

    def test_target_healthy_nochange(self):
        for value in ("OK", "NO_CHANGE", "STALE_OK:NO_CHANGE"):
            good, _ = evaluate(from_tsv(f"icheon\t{value}\n"), "icheon")
            self.assertTrue(good)

    def test_target_wrong_source_or_missing_extra_statuses(self):
        self.assertFalse(evaluate(from_tsv("ansan\tOK\n"), "icheon")[0])
        self.assertFalse(evaluate(from_tsv("icheon\tOK\nansan\tOK\n"), "icheon")[0])

    def test_full_batch_partial_preserves_successful_data(self):
        good, msg = evaluate(from_tsv("icheon\tOK\nansan\tSTALE_OK:STRICT_QA\n"))
        self.assertTrue(good)
        self.assertIn("DEGRADED", msg)

    def test_full_batch_all_fail_or_stale_is_failure(self):
        self.assertFalse(evaluate(from_tsv("icheon\tSTALE_OK:INGEST\nansan\tDISCOVERY_FAILED\n"))[0])

if __name__ == "__main__":
    unittest.main()
