"""P4 review must not invent geolocations or approve bank/payment identities."""
import unittest
from p4_map_gap_review import assess, build, mapped, markdown


class P4ReviewTests(unittest.TestCase):
    def sample(self, name, visits, address="", source="", **extra):
        row = {"name": name, "origin": "테스트시", "jurisdiction": "대한민국",
               "address": address, "evidence": {"visits": visits, "months": 3,
               "spend": visits * 20000, "recent": [{"source": source}]}}
        row.update(extra)
        return row

    def test_map_verification_reuses_coordinate_gate(self):
        geo = {"동명식당|테스트시": {"lat": 37.1, "lon": 127.1,
               "match_mode": "name", "result_name": "동명식당", "score": 100}}
        self.assertFalse(mapped(self.sample("동명식당", 10), geo))
        self.assertTrue(mapped({"name": "확인된가게", "source_verified_coordinate": True,
                               "lat": 37.1, "lon": 127.1}, geo))

    def test_missing_address_never_auto_approves(self):
        a = assess(self.sample("독특한식당", 21, source="https://official.example/records"))
        self.assertEqual(a["review_status"], "OFFICIAL_EXPENSE_SOURCE_MUST_BE_CHECKED_FOR_ADDRESS")
        self.assertFalse(a["payment_branch_verified"])
        self.assertFalse(a["individual_attendance_verified"])
        self.assertFalse(a["location_promoted"])
        self.assertFalse(a["published_address"])

    def test_street_address_needs_safe_location_check(self):
        a = assess(self.sample("분점", 10, address="서울 영등포구 여의대로 12"))
        self.assertEqual(a["review_status"], "PUBLISHED_ADDRESS_NEEDS_GEOCODE_OR_IDENTITY_REVIEW")

    def test_queue_contains_only_unmapped_and_is_deterministic(self):
        records = [self.sample("A", 1), self.sample("B", 100),
                   {"name": "C", "lat": 37.1, "lon": 127.1, "source_verified_coordinate": True}]
        doc = build(records, {}, 2)
        self.assertEqual((doc["total_published_venues"], doc["safe_map_venues"], doc["unmapped_venues"]), (3, 1, 2))
        self.assertEqual([x["merchant"] for x in doc["candidates"]], ["B", "A"])
        self.assertEqual(doc["approved_for_map_addition"], 0)
        self.assertIn("지도 미표시", markdown(doc))
        with self.assertRaises(ValueError):
            build(records, {}, 0)

    def test_non_https_links_not_treated_as_official_evidence(self):
        x = assess(self.sample("D", 1, source="http://example.com/path"))
        self.assertEqual(x["source_urls"], [])
        self.assertEqual(x["review_status"], "MISSING_ADDRESS_AND_TRACEABLE_SOURCE")


if __name__ == "__main__":
    unittest.main()
