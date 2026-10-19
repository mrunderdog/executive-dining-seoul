import unittest
from localdata_regions import building_key,route_localdata,summarize_coverage
class RegionRouteTests(unittest.TestCase):
    def test_disambiguates_same_named_district(self):
        self.assertEqual(route_localdata("서울특별시 중구 세종대로 12"),("서울중구","3010000"))
        self.assertEqual(route_localdata("부산광역시 중구 중앙대로 12"),("부산중구","3250000"))
    def test_routes_localdata_metropolitan_and_provincial(self):
        self.assertEqual(route_localdata("서울특별시 강남구 테헤란로 123"),("서울강남구","3220000"))
        self.assertEqual(route_localdata("경기도 성남시 분당구 판교역로 100"),("경기성남시","3780000"))
        self.assertEqual(route_localdata("경기도 수원시 팔달구 인계로 98"),("경기수원시","3740000"))
        self.assertEqual(route_localdata("서울특별시 서대문구 통일로9안길 36-3"),("서울서대문구","3120000"))
        self.assertEqual(route_localdata("충청북도 청주시 상당구 상당로 88"),("충북청주시","5710000"))
    def test_recover_explicit_unambiguous_locality_without_guessing(self):
        self.assertEqual(route_localdata("서울시 서초중앙로 188 아크로비스타상가"),None)
        self.assertEqual(route_localdata("서울영등포구국회대로70길7(여의도동,동아빌딩)지하1층"),("서울영등포구","3180000"))
        self.assertEqual(route_localdata("서초구 강남대로"),("서울서초구","3210000"))
        self.assertEqual(route_localdata("은평구 녹번로 12"),("서울은평구","3110000"))
        self.assertEqual(route_localdata("양천구 등촌로 216"),("서울양천구","3140000"))
        self.assertEqual(route_localdata("강서구 공항대로 635"),None)
        self.assertIsNone(route_localdata("중구 통일로 78"))
        self.assertIsNone(route_localdata("전국 공공기관"))
    def test_building_key_never_aliases_across_regions(self):
        a=building_key("서울특별시 중구 통일로 78, 1층")
        b=building_key("부산광역시 중구 통일로 78")
        self.assertNotEqual(a,b)
        self.assertEqual(a,"3010000|통일로78")
        self.assertNotEqual(building_key("서울특별시 중구 통일로 78"),building_key("서울특별시 중구 통일로 78-1"))
    def test_legacy_zero_at_building_normalization_is_lookup_only(self):
        self.assertEqual(building_key("경기 의정부시 동일로 131-0@ 1층"),
                         building_key("경기도 의정부시 동일로 131, 1층"))
        self.assertEqual(building_key("경기 의정부시 동일로192번길 28-41@"),
                         building_key("경기도 의정부시 동일로192번길 28-41"))
        self.assertNotEqual(building_key("경기 의정부시 동일로 131-1@"),
                            building_key("경기 의정부시 동일로 131"))
        self.assertNotEqual(building_key("경기 의정부시 동일로 131-0"),
                            building_key("경기 의정부시 동일로 131"))

    def test_unknown_regions_are_not_guessed(self):
        self.assertIsNone(route_localdata("중구 통일로 78"))
        self.assertIsNone(route_localdata("전국 공공기관"))
        self.assertEqual(building_key("서울특별시 중구"),"")
    def test_coverage_conservation(self):
        x=summarize_coverage([{"name":"A","address":"서울특별시 중구 통일로 78","origin":"서울시"},
                              {"name":"B","address":"경기도 성남시 분당구 판교역로 20","origin":"경기도"},
                              {"name":"C","address":""}])
        self.assertEqual(x["total_published_venues"],3)
        self.assertEqual(x["routed_venues"],2)
        self.assertEqual(x["road_building_verifiable"],2)
        self.assertEqual(x["unrouted_venues"],1)
        self.assertEqual(x["unrouted_reason_counts"]["MISSING_ADDRESS"],1)
        self.assertEqual(len(x["unrouted_review_queue"]),1)
        self.assertEqual(x["unrouted_review_queue"][0]["reason"],"MISSING_ADDRESS")
    def test_per_origin_gap_reporting_never_infers_address(self):
        x=summarize_coverage([
            {"name":"A","address":"","origin":"중앙정부","evidence":{"visits":8}},
            {"name":"B","address":"중구 임의로 99","origin":"중앙정부","evidence":{"spending_events":2}},
            {"name":"C","address":"서울특별시 중구 세종대로 12","origin":"서울시청"}])
        self.assertEqual(x["total_published_venues"],3)
        self.assertEqual(x["unrouted_reason_counts"],{"MISSING_ADDRESS":1,"UNROUTABLE_JURISDICTION":1})
        by={r["origin"]:r for r in x["unrouted_by_origin"]}
        self.assertEqual(by["중앙정부"]["MISSING_ADDRESS"],1)
        self.assertEqual(by["중앙정부"]["UNROUTABLE_JURISDICTION"],1)
        self.assertEqual(x["unrouted_review_queue"][0]["reported_usage_events"],8)
        self.assertEqual(x["unrouted_review_queue"][0]["address"],"")
if __name__=="__main__":unittest.main()
