"""Fail-closed source pinning for scanned official Yongin expense PDF."""
import hashlib
import unittest

from review_scanned_yongin_pdf import verify_original


class ScannedYonginReviewSafety(unittest.TestCase):
    def test_reject_changed_official_bytes_before_ocr(self):
        with self.assertRaisesRegex(ValueError, "official_pdf_sha256_mismatch"):
            verify_original(b"%PDF-1.7\nnot the verified source")

    def test_reject_non_pdf_even_if_digest_matches_explicit_input(self):
        raw = b"pretend document bytes"
        with self.assertRaisesRegex(ValueError, "verified_source_not_pdf"):
            verify_original(raw, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    unittest.main()
