import unittest
from rank_localdata_expansion import build

class PriorityTests(unittest.TestCase):
    def test_prioritization_and_semantics(self):
        def region(name,good,bad,origins):
            return {"region":name,"orgCode":"1234567","venues":good+bad,
                "with_road_building":good,"missing_road_building":bad,
                "institution_origin_count":origins}
        src={"regions":[region("서울중구",9,0,2),
                         region("부산해운대구",10,1,4),
                         region("강원춘천시",5,0,2),
                         region("경남거제시",0,7,2)],
             "total_published_venues":32,"routed_venues":32,
             "road_building_verifiable":24,"unrouted_venues":0}
        result=build(src)
        self.assertEqual(result["next_candidate_regions"],["부산해운대구","강원춘천시"])
        self.assertFalse(any(r["official_license_verified"] for r in result["candidate_jurisdictions"]))
        self.assertEqual(result["candidate_jurisdictions"][-1]["region"],"서울중구")
        self.assertEqual(next(r for r in result["candidate_jurisdictions"] if r["region"]=="경남거제시")["next_action"],"FIX_SOURCE_ADDRESSES")
    def test_reject_inconsistent_regions(self):
        with self.assertRaises(ValueError):
            build({"regions":[{"region":"X","venues":2,"with_road_building":3,
                "missing_road_building":0}],"total_published_venues":2,
                "unrouted_venues":0})
if __name__=="__main__": unittest.main()
