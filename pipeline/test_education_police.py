"""Synthetic, offline contract tests: verify no title-only or aggregate-only publication."""
import unittest

from leadership_scope import classify_leadership_title, valid_transaction
from education_police_source_probe import discover_post_links, discover_attachments, extract_post_id
from ingest_education_police_expense import process
from gyeonggi_education_pdf import normalize_table

class LeadershipTests(unittest.TestCase):
    def test_education_roles(self):
        for title, tier in [
            ("2026년 2분기 교육감 업무추진비", "education_head"),
            ("2026년 2분기 제1부교육감 업무추진비", "education_deputy"),
            ("2026년 2분기 기획조정실장 업무추진비", "director_general"),
            ("2026년 2분기 행정국장 업무추진비", "director_general"),
            ("OO교육지원청 교육장 업무추진비", "education_branch_head"),
            ("OO본부장 업무추진비", "director_general"),
        ]:
            self.assertEqual(classify_leadership_title(title, "education_leadership")["tier"], tier)
    def test_police_roles(self):
        for title, tier in [
            ("2026년 경찰청장 업무추진비", "police_head"),
            ("2026년 8월 경찰청차장 업무추진비", "police_deputy"),
            ("2026년 8월 경무인사기획관 업무추진비", "police_bureau_head"),
            ("2026년 4월 경비국장 업무추진비", "police_bureau_head"),
            ("2026년 국가수사본부장 업무추진비", "police_bureau_head"),
        ]:
            self.assertEqual(classify_leadership_title(title, "police_leadership")["tier"], tier)
    def test_exclude_unscoped(self):
        for title in ["2026년 4월 정책과장 업무추진비", "2026년 일반직원 업무추진비",
                      "2026년 교육감 업무집행 통계", "2026년 실국장 참석 업무추진비(부서별)"]:
            self.assertIsNone(classify_leadership_title(title, "education_leadership"))
    def test_post_links_and_host_restriction(self):
        page = '<a href="/goe/na/ntt/selectNttInfo.do?bbsId=1956&amp;nttSn=123456">2026년 행정국장 업무추진비 집행내역 공개</a>'
        found = discover_post_links(page, "https://www.goe.go.kr/goe/na/ntt/selectNttList.do?bbsId=1956",
                                    "education_leadership","education",{"goe.go.kr"})
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["detail_url"].endswith("nttSn=123456"))
        self.assertEqual(extract_post_id({"onclick": "view(20260325092542533)"}, "police"), "20260325092542533")
        detail = '<a href="https://malicious.example/steal.pdf">test.pdf</a><a href="/resource/doc.pdf">data.pdf</a>'
        self.assertEqual(len(discover_attachments(detail, "https://www.goe.go.kr/page", {"goe.go.kr"})), 1)
        preview = """<a href="javascript:void(0);" onclick="previewAjax('https://www.goe.go.kr/resource/goe/na/bbs_1955/2026/07/example.pdf','2026 education.pdf')">미리보기</a>"""
        extracted = discover_attachments(preview, "https://www.goe.go.kr/detail", {"goe.go.kr"})
        self.assertEqual(len(extracted), 1)
        self.assertTrue(extracted[0]["url"].endswith("/example.pdf"))
    def test_gyeonggi_actual_eight_column_pdf_layout(self):
        table = [
            ["부서", "집행일", "집행시간", "적 요", "액", "채 주(실거래처)", "집행대상", "집행방법"],
            ["교육감", "2026-04-01", "13:43", "교육현안 협의회비", "55,800", "화월청과", "외부 관계자 10명", "카드"],
            [None, None, "12:32", None, "158,000", "더615(동류수)", None, None],
            ["교육감", "2026-04-03", "11:00", "업무협의", "150,000", "능라도", "관계자 5명", "카드"],
        ]
        rows=normalize_table(table,"https://www.goe.go.kr/source.pdf",1,1)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]["amount"],55800)
        self.assertEqual(rows[1]["used_date"],"2026-04-01")
        self.assertEqual(rows[1]["merchant"],"더615(동류수)")
        self.assertEqual(rows[2]["people"],5)

    def test_staging_rejects_invalid_transactions(self):
        src = {"key":"gyeonggi_education", "institution":"경기도교육청",
               "cohort":"education_leadership","official_hosts":["goe.go.kr"]}
        post = {"title":"2026년 2분기 행정국장 업무추진비 공개","tier":"director_general","detail_url":"https://www.goe.go.kr/detail"}
        good = {"used_date":"2026-04-02","amount":150000,"merchant":"능라도","source_url":"https://www.goe.go.kr/file.pdf"}
        bad = {**good, "merchant":"배달의민족"}
        accepted,stats=process([good,bad],src,post,good["source_url"])
        self.assertEqual(stats["accepted"],1)
        self.assertEqual(len(accepted),1)
        self.assertEqual(accepted[0]["publication_status"],"STAGING_ONLY")
        fake={**good,"source_url":"https://www.goe.go.kr.evil.com/file.pdf","role":"행정국장","role_source":"posting_title"}
        self.assertFalse(valid_transaction(fake, {"goe.go.kr"}))

if __name__ == "__main__":
    unittest.main()
