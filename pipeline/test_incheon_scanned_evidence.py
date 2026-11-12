"""Do not override the original scan's inconsistent subtotal with inferred money."""
import json
import unittest
from pathlib import Path

EVIDENCE=Path(__file__).resolve().parent/"incheon_scan_original_evidence.json"

class IncheonScanSourceTests(unittest.TestCase):
    def test_original_source_sha_and_discrepancy_are_preserved(self):
        doc=json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertFalse(doc["publish"])
        rows={x["msg_seq"]:x for x in doc["documents"]}
        self.assertEqual(set(rows),{1321,1329})
        for source in rows.values():
            self.assertEqual(len(source["sha256"]),64)
            self.assertEqual(source["visual_row_total_krw"],sum(v[1] for v in source["visually_read_date_amounts"]))
            self.assertEqual(source["printed_minus_rows_krw"],source["printed_total_krw"]-source["visual_row_total_krw"])
            self.assertEqual(source["printed_transactions"],len(source["visually_read_date_amounts"]))
        self.assertEqual(rows[1321]["printed_minus_rows_krw"],438200)
        self.assertEqual(rows[1321]["source_mismatch_status"],"HOLD_PRINTED_TOTAL_DIFFERS_FROM_ROW_SUM")
        self.assertEqual(rows[1329]["printed_minus_rows_krw"],0)
        self.assertEqual(rows[1329]["printed_total_krw"],784000)

if __name__=="__main__":
    unittest.main()
