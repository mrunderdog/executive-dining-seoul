import unittest
from publish_education_police import select, preserve_last_good
from extra_published import education_police_records
class PublicationContract(unittest.TestCase):
    def setUp(self):
        self.sources={"sources":[{"key":"incheon_education","institution":"인천광역시교육청","official_hosts":["ice.go.kr"]}]}
        self.manifest={"venues":[{"source_key":"incheon_education","merchant":"판다칸칸","address":"인천 남동구 논고개로 80",
          "verification_confidence":"HIGH","sources":["https://example.org/a","https://example.org/b"],
          "allowed_roles":["교육감"],"category":"중식"}]}
        self.base={"source_key":"incheon_education","merchant":"판다칸칸","role":"교육감",
          "used_date":"2026-08-03","amount":400000,"row_id":"proof1",
          "target":"교육감, 교육관계자 등 총 12명",
          "source_url":"https://www.ice.go.kr/docs/real.xlsx",
          "source_detail_url":"https://www.ice.go.kr/ice/na/ntt/selectNttInfo.do?nttSn=11111",
          "role_source":"posting_title","publication_status":"STAGING_ONLY"}
    def test_publish_verified(self):
        a=select([self.base],self.manifest,self.sources)
        self.assertEqual(a["approved_venues"],1)
        self.assertEqual(a["approved_transactions"],1)
        self.assertEqual(a["venues"][0]["transactions"][0]["amount"],400000)
    def test_truncated_board_preserves_verified_previous_venue(self):
        prior=select([self.base],self.manifest,self.sources)
        current=select([],self.manifest,self.sources)
        out=preserve_last_good(current,prior,self.manifest,self.sources)
        self.assertEqual(out["approved_venues"],1)
        self.assertEqual(out["approved_transactions"],1)
        self.assertEqual(out["last_good_preserved_transactions"],1)
        self.assertTrue(out["venues"][0]["transactions"][0]["carried_forward_from_last_good"])
    def test_old_venue_requires_unchanged_address_and_manifest(self):
        previous=select([self.base],self.manifest,self.sources)
        altered={"venues":[{**self.manifest["venues"][0],"address":"인천 다른 주소 123"}]}
        out=preserve_last_good(select([],altered,self.sources),previous,altered,self.sources)
        self.assertEqual(out["approved_venues"],0)
        out=preserve_last_good(select([],{"venues":[]},self.sources),previous,{"venues":[]},self.sources)
        self.assertEqual(out["approved_venues"],0)
    def test_previous_data_must_retain_explicit_official_evidence(self):
        previous=select([self.base],self.manifest,self.sources)
        previous["venues"][0]["transactions"][0]["target"]="교육감실 직원 10명"
        result=preserve_last_good(select([],self.manifest,self.sources),previous,self.manifest,self.sources)
        self.assertEqual(result["approved_transactions"],0)
    def test_current_and_prior_transaction_merge_without_duplication(self):
        previous=select([self.base],self.manifest,self.sources)
        new={**self.base,"row_id":"proof2","used_date":"2026-09-03","amount":120000}
        current=select([self.base,new],self.manifest,self.sources)
        result=preserve_last_good(current,previous,self.manifest,self.sources)
        self.assertEqual(result["approved_transactions"],2)
        self.assertEqual(result["last_good_preserved_transactions"],0)
    def test_no_attendance_inference(self):
        bad={**self.base,"target":"교육감실 직원 12명"}
        self.assertEqual(select([bad],self.manifest,self.sources)["approved_venues"],0)
    def test_address_and_site_required(self):
        for b in [{**self.manifest["venues"][0],"sources":["https://x"]},
                  {**self.manifest["venues"][0],"address":""}]:
            self.assertEqual(select([self.base],{"venues":[b]},self.sources)["approved_venues"],0)
    def test_unrecognized_or_external(self):
        for bad in [{**self.base,"merchant":"같은이름 다른식당"},{**self.base,"source_url":"https://ice.go.kr.evil.test/xlsx"}]:
            self.assertEqual(select([bad],self.manifest,self.sources)["approved_venues"],0)
    def test_never_publish_unscoped_role(self):
        self.assertEqual(select([{**self.base,"role":"과장"}],self.manifest,self.sources)["approved_venues"],0)
if __name__=="__main__":unittest.main()
