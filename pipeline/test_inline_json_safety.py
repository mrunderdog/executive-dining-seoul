"""Regression coverage for JSON embedded in HTML script elements."""
import unittest

from build_site import inline_json


class InlineJsonSafetyTests(unittest.TestCase):
    def test_script_breakout_is_neutralized(self):
        sample = {"merchant": "</script><script>alert(1)</script>", "text": "A&B<Gold>"}
        output = inline_json(sample)
        self.assertNotIn("</script", output.lower())
        self.assertNotIn("<script", output.lower())
        self.assertNotIn("<", output)
        self.assertNotIn(">", output)
        self.assertNotIn("&", output)
        self.assertIn(r"\u003c/script\\u003e", output)

    def test_line_separators_remain_valid_escaped_json(self):
        output = inline_json({"text": "a\u2028b\u2029c"})
        self.assertIn(r"\u2028", output)
        self.assertIn(r"\u2029", output)
        self.assertNotIn("\u2028", output)
        self.assertNotIn("\u2029", output)

    def test_unicode_and_nested_payload_survive_roundtrip(self):
        import json
        payload = {"업소": "금&식당", "arr": ["<tag>", {"value": 17}]}
        self.assertEqual(json.loads(inline_json(payload)), payload)


if __name__ == "__main__":
    unittest.main()
