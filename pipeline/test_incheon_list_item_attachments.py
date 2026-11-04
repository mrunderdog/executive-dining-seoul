"""Real official 2026-11 Incheon list-item markup regression fixtures."""
import unittest
from unittest.mock import patch
from capital_backfill import SOURCES, discover_source, incheon_listing_row_posts

SRC = next(s for s in SOURCES if s.key == "incheon_council")
BASE = SRC.listing_template.format(page=1)

def item(seq, title, file_seq=None, compress=False):
    if file_seq is None:
        file_seq = seq
    file_path = ("bbsMsgFileDownCompress.do?bcd=infordisc&msg_seq=" + str(file_seq)
                 if compress else
                 "bbsMsgFileDown.do?bcd=infordisc&msg_seq=" + str(file_seq) + "&fileno=1")
    return (f'<li><p class="title" title="제목"><a href="/main/bbs/bbsMsgDetail.do?msg_seq={seq}&amp;bcd=infordisc&amp;pgno=1">'
            f'{title}</a></p><div class="writer_info"><ul><li class="file">'
            f'<a href="/main/bbs/{file_path}" target="_blank"><img alt="첨부파일 다운받기"></a>'
            '</li></ul></div></li>')

class OfficialListItemTests(unittest.TestCase):
    def test_real_same_item_file_survives_detail_unreachable(self):
        html = '<ul class="generalList">' + item(1333, "2026년 10월 예산결산특별위원장 업무추진비 집행내역") + '</ul>'
        parsed = incheon_listing_row_posts(SRC, BASE, html, (2026,7), (2026,10))
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["discovery_method"], "official_same_list_item")
        self.assertIn("msg_seq=1333", parsed[0]["attachments"][0]["url"])
        self.assertIn("fileno=1", parsed[0]["attachments"][0]["url"])
        with patch("capital_backfill.fetch_text", side_effect=lambda u: html if u == BASE else "") as fetch:
            found = discover_source(SRC, (2026,10), (2026,10))
        self.assertEqual(len(found), 1)
        self.assertFalse(any("bbsMsgDetail.do" in str(call.args[0]) for call in fetch.call_args_list))

    def test_cross_row_file_link_never_assigned_to_different_post(self):
        html = ('<ul class="generalList">'
                + item(1327, "2026년 9월 환경교통위원장 업무추진비 집행내역", file_seq=1326)
                + item(1326, "2026년 9월 의회운영위원장 업무추진비 집행내역") + '</ul>')
        posts = incheon_listing_row_posts(SRC, BASE, html, (2026,9), (2026,9))
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0]["attachments"], [])
        self.assertTrue(posts[0].get("error"))
        self.assertEqual(len(posts[1]["attachments"]), 1)

    def test_compressed_multi_file_route_is_only_source_observed_url(self):
        html = '<ul class="generalList">' + item(1328, "2026년 3분기(7월~9월) 의장단 업무추진비 집행내역", compress=True) + '</ul>'
        posts = incheon_listing_row_posts(SRC, BASE, html, (2026,7), (2026,9))
        self.assertEqual(len(posts), 1)
        self.assertIn("bbsMsgFileDownCompress.do", posts[0]["attachments"][0]["url"])
        self.assertNotIn("fileno=", posts[0]["attachments"][0]["url"])

    def test_no_download_is_explicit_hold(self):
        html = ('<li><p class="title"><a href="/main/bbs/bbsMsgDetail.do?msg_seq=1324&amp;bcd=infordisc">'
                '2026년 9월 행정안전위원장 업무추진비 집행내역</a></p>'
                '<div class="writer_info"></div></li>')
        posts = incheon_listing_row_posts(SRC, BASE, html, (2026,9), (2026,9))
        self.assertEqual(len(posts), 1)
        self.assertTrue(posts[0].get("error"))

if __name__ == "__main__":
    unittest.main()
