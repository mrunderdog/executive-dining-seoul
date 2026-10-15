import unittest
from build_license_review_queue import build

class ReviewQueueTests(unittest.TestCase):
    def test_categorize_without_promotion(self):
        data={"geographic_scope":["서울강북구"],"total_venues":4,"sources":[],
              "venues":[
                 {"license_match_status":"NOT_MATCHED","merchant":"가","address":"경기 의정부시 동일로 131-0@",
                  "official_building_business_count":0,"official_building_businesses":[]},
                 {"license_match_status":"NOT_MATCHED","merchant":"나","address":"서울 강북구 도봉로 10",
                  "official_building_business_count":1,"official_building_businesses":[{"license_name":"나다","license_address":"서울 강북구 도봉로 10"}]},
                 {"license_match_status":"NOT_MATCHED","merchant":"다","address":"서울 강북구 도봉로 12",
                  "official_building_business_count":0,"official_building_businesses":[]},
                 {"license_match_status":"NAME_AND_BUILDING_ADDRESS_FLOOR_UNVERIFIED","merchant":"라",
                  "address":"서울 강북구 도봉로 14"}]}
        out=build(data)
        self.assertEqual(out["unmatched_count"],3)
        self.assertEqual(out["review_reason_counts"],{"ADDRESS_FORMAT_REVIEW":1,
             "SAME_BUILDING_NAME_REVIEW":1,"NO_SAME_BUILDING_CANDIDATE":1})
        self.assertTrue(all(x["payment_branch_identity"]=="NOT_VERIFIED" and
            x["personal_attendance"]=="NOT_ESTABLISHED" for x in out["review_queue"]))
if __name__=="__main__":unittest.main()
