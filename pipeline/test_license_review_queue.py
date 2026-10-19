import unittest
from build_license_review_queue import build

class QueueTest(unittest.TestCase):
    def test_unmatched_only_and_never_promote(self):
        audit={"geographic_scope":["서울강북구"],"total_venues":4,"sources":[{"district":"서울강북구","sha256":"source"}],"venues":[
            {"license_match_status":"NOT_MATCHED","merchant":"가","address":"서울 강북구 131-0@"},
            {"license_match_status":"NOT_MATCHED","merchant":"나","address":"서울 강북구 도봉로 10","official_building_business_count":1,
             "official_building_businesses":[{"license_name":"나다","license_address":"서울 강북구 도봉로 10"}]},
            {"license_match_status":"NOT_MATCHED","merchant":"다","address":"서울 강북구 도봉로 12"},
            {"license_match_status":"EXACT_NAME_AND_ADDRESS","merchant":"라"}]}
        x=build(audit)
        self.assertEqual(x["unmatched_count"],3)
        self.assertEqual(x["review_reason_counts"],{"ADDRESS_FORMAT_REVIEW":1,"SAME_BUILDING_NAME_REVIEW":1,"NO_SAME_BUILDING_CANDIDATE":1})
        self.assertEqual(len(x["source_provenance"]),1)
        self.assertTrue(all(v["payment_branch_identity"]=="NOT_VERIFIED" and v["personal_attendance"]=="NOT_ESTABLISHED" for v in x["review_queue"]))

if __name__=="__main__":
    unittest.main()
