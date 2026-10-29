"""P1 official source discovery regressions, preserving strict file provenance."""
import unittest
from unittest.mock import patch

from capital_backfill import SOURCES, discover_source, title_period

class CouncilSourceP1Tests(unittest.TestCase):
    def test_trailing_quarter_with_early_year(self):
        self.assertEqual(title_period("2026년 파주시의회 업무추진비 내역(2분기)"),(2026,None,2))
        self.assertEqual(title_period("2026년 파주시의회 업무추진비 내역(1분기)"),(2026,None,1))
        self.assertEqual(title_period("2025년 파주시의회 교섭단체 집행내역(4분기)"),(2025,None,4))
        self.assertIsNone(title_period("파주시의회 업무추진비 내역(2분기)"))

    def test_gapyeong_list_attachment_binds_only_exact_official_row(self):
        src=next(s for s in SOURCES if s.key=="gapyeong")
        url=src.listing_template.format(page=1)
        detail="https://www.gpassem.go.kr/kr/operations2BBSview.do?uid=D62A1C9FEF421AC0A2CBF93AB69FDAED&flag=all&page=1"
        file="https://www.gpassem.go.kr/kr/bbs/download.do?bbs_id=operations2&uid=C6D2F5739D9F2079ED0F6F7E1D0469C0"
        another="https://www.gpassem.go.kr/kr/bbs/download.do?bbs_id=operations2&uid=DIFFERENT"
        listing=f"""<table><tr><td><a href="{detail}">2026년도 2분기 업무추진비 사용내역</a></td>
        <td><a href="{file}">2분기 업무추진비.pdf</a></td></tr>
        <tr><td><a href="/kr/operations2BBSview.do?uid=other">2025년도 1분기 업무추진비</a></td>
        <td><a href="{another}">다른 기간 파일</a></td></tr></table>"""
        def fetch(x):
            return listing if x==url else "<p>첨부파일 PDF 뷰어 전용</p>"
        with patch("capital_backfill.fetch_text",side_effect=fetch):
            got=discover_source(src,(2026,4),(2026,6))
        relevant=[p for p in got if p.get("post_url")==detail]
        self.assertEqual(len(relevant),1,got)
        self.assertEqual(len(relevant[0]["attachments"]),1,relevant)
        self.assertIn("C6D2F573",relevant[0]["attachments"][0]["url"])
        self.assertTrue(all("DIFFERENT" not in str(p) for p in relevant))

    def test_gapyeong_cannot_accept_unrelated_file_url(self):
        src=next(s for s in SOURCES if s.key=="gapyeong")
        u=src.listing_template.format(page=1)
        detail="https://www.gpassem.go.kr/kr/operations2BBSview.do?uid=D62A1C9FEF421AC0A2CBF93AB69FDAED"
        html=f'<tr><td><a href="{detail}">2026년도 2분기 업무추진비 사용내역</a></td><td><a href="https://evil.invalid/kr/bbs/download.do?bbs_id=operations2&uid=fake">fake.pdf</a></td></tr>'
        with patch("capital_backfill.fetch_text",side_effect=lambda target: html if target==u else "<p>no file</p>"):
            got=discover_source(src,(2026,4),(2026,6))
        self.assertEqual([p["attachments"] for p in got if p.get("post_url")==detail],[[]])

if __name__=="__main__":unittest.main()
