import json
import tempfile
import unittest
from pathlib import Path

from build_verified_transactions import verified_ledger
from qa_council_publication import assess


def fixture(root):
    (root / "data" / "raw").mkdir(parents=True)
    (root / "reports").mkdir()
    source = "sample"
    post = "https://example.gov/council/post/123"
    file = "https://example.gov/download?id=456"
    rows = [{
        "row_id": str(i), "source_key": source,
        "source_post_url": post, "source_attachment_url": file,
        "source_period": [2026, 9, None], "used_date": f"2026-09-{i + 10:02d}",
        "institution": "시험시의회", "merchant": "가게명", "role": "의장",
        "amount": 1000 + i, "purpose": "공식 사용 내역",
    } for i in range(5)]
    payload = {"source": source, "rows": rows,
               "files": [{"url": file, "sha256": "b" * 64, "bytes": 100}]}
    discovery = {"posts": [{"source": source, "post_url": post,
                            "institution": "시험시의회", "jurisdiction": "시험시",
                            "attachments": [{"url": file}]}]}
    (root / "data" / "raw" / "sample_expense.json").write_text(json.dumps(payload), encoding="utf-8")
    (root / "reports" / "capital-backfill-discovery-sample.json").write_text(json.dumps(discovery), encoding="utf-8")
    return payload, discovery


class VerifiedLedgerTests(unittest.TestCase):
    def test_only_fully_verified_source_is_included(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root)
            result = verified_ledger(root, "2026-10-20T00:00:00Z")
            self.assertEqual(result["verified_row_count"], 5)
            self.assertEqual(result["verified_source_count"], 1)
            self.assertEqual(result["verified_total_amount"], 5010)
            self.assertEqual(result["rows"][0]["used_date"], "2026-09-14")
            self.assertTrue(all(r["source_attachment_url"].startswith("https://") for r in result["rows"]))

    def test_one_bad_date_or_amount_holds_the_entire_source(self):
        for field, bad in (("used_date", "2026-10-01"), ("amount", 0), ("merchant", "합계")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                payload, _ = fixture(root)
                payload["rows"][0][field] = bad
                (root / "data" / "raw" / "sample_expense.json").write_text(json.dumps(payload), encoding="utf-8")
                result = verified_ledger(root)
                self.assertEqual(result["verified_row_count"], 0)
                self.assertEqual(result["held_source_count"], 1)
                self.assertEqual(result["rows"], [])

    def test_forged_institution_holds_entire_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload, _ = fixture(root)
            payload["rows"][0]["institution"] = "다른기관"
            (root / "data" / "raw" / "sample_expense.json").write_text(json.dumps(payload), encoding="utf-8")
            result = verified_ledger(root)
            self.assertEqual(result["verified_row_count"], 0)
            self.assertEqual(result["held_source_count"], 1)

    def test_real_ansan_source_is_full_qa_included(self):
        root = Path(__file__).resolve().parents[1]
        result = verified_ledger(root)
        raw = json.loads((root / "data" / "raw" / "ansan_expense.json").read_text(encoding="utf-8"))
        discovery = json.loads((root / "reports" / "capital-backfill-discovery-ansan.json").read_text(encoding="utf-8"))
        gate = assess("ansan", raw, discovery)
        ansan = next((s for s in result["sources"] if s["source_key"] == "ansan"), None)
        if gate["status"] == "PUBLISH_READY":
            self.assertIsNotNone(ansan)
            self.assertEqual(ansan["rows"], len(raw["rows"]))
        else:
            self.assertIsNone(ansan)
        self.assertEqual(result["verified_row_count"], sum(s["rows"] for s in result["sources"]))
        self.assertTrue(all(s["source_key"] not in {h["source_key"] for h in result["held_sources"]}
                            for s in result["sources"]))


if __name__ == "__main__":
    unittest.main()
