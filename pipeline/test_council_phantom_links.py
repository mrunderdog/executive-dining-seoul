"""Regression tests for phantom expense posts from self-linked file labels."""
import unittest
from unittest.mock import patch
from capital_backfill import SOURCES, discover_source

class PhantomListingLinkTests(unittest.TestCase):
    def test_self_linked_download_labels_never_become_posts(self):
        cases = {
            "gunpo": ('https://www.gunpocouncil.go.kr/kr/costBBSview.do?uid=414146443ABE04A0211258F9C8ABD628',
                      '2026년 8월 업무추진비 공개'),
            "michuhol": ('https://www.michuhol.go.kr/ndsys/ndBBs/bbs_view.asp?bbs_code=board_189&seq=121',
                         '의장단 업무추진비 사용내역2026. 9월'),
            "incheon_council": ('https://www.icouncil.go.kr/main/bbs/bbsMsgDetail.do?msg_seq=1329&bcd=infordisc',
                                '2026년 9월 문화복지위원장 업무추진비 집행내역'),
        }
        for key, (detail_url, title) in cases.items():
            with self.subTest(source=key):
                src = next(s for s in SOURCES if s.key == key)
                listing_url = src.listing_template.format(page=1)
                listing = (f'<a href="{detail_url}">{title}</a>'
                           f'<a href="{listing_url}">2026년 9월 업무추진비.xlsx 파일 내려받기</a>')
                detail = '<a href="https://example.invalid/irrelevant.pdf">unrelated</a>'
                with patch("capital_backfill.fetch_text",
                           side_effect=lambda url: listing if url == listing_url else detail):
                    posts = discover_source(src, (2026, 8), (2026, 9))
                self.assertFalse(any(p.get("post_url") == listing_url for p in posts), posts)
                self.assertTrue(any(p.get("post_url") == detail_url for p in posts), posts)

    def test_real_direct_file_link_remains_discoverable(self):
        src = next(s for s in SOURCES if s.key == "gunpo")
        listing_url = src.listing_template.format(page=1)
        file_url = "https://www.gunpocouncil.go.kr/kr/bbs/download.do?bbs_id=cost&uid=A1B2C3"
        listing = f'<a href="{file_url}">2026년 8월 업무추진비.xlsx</a>'
        with patch("capital_backfill.fetch_text", return_value=listing):
            posts = discover_source(src, (2026, 8), (2026, 8))
        self.assertEqual(len(posts), 1, posts)
        self.assertEqual(posts[0]["attachments"][0]["url"], file_url)

if __name__ == "__main__":
    unittest.main()
