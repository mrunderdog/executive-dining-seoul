"""Fail-closed source pinning for scanned official Yongin expense PDF."""
import hashlib
import unittest

from review_scanned_yongin_pdf import verify_original, verified_page_controls


class ScannedYonginReviewSafety(unittest.TestCase):
    def test_visually_audited_source_counts_and_amount_control(self):
        controls = verified_page_controls()
        self.assertEqual([p["source_rows"] for p in controls["pages"]], [2, 7, 9, 4, 6, 16])
        self.assertEqual(controls["expected_official_rows"], 44)
        self.assertEqual(controls["expected_official_amount_krw"], 6954740)
        self.assertEqual(controls["unidentified_venue"]["source_row_numbers"], [1, 2, 3, 4, 5, 6])
        self.assertEqual(controls["publication_status"], "NOT_APPROVED")

    def test_reject_changed_official_bytes_before_ocr(self):
        with self.assertRaisesRegex(ValueError, "official_pdf_sha256_mismatch"):
            verify_original(b"%PDF-1.7\nnot the verified source")

    def test_reject_non_pdf_even_if_digest_matches_explicit_input(self):
        raw = b"pretend document bytes"
        with self.assertRaisesRegex(ValueError, "verified_source_not_pdf"):
            verify_original(raw, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    unittest.main()
