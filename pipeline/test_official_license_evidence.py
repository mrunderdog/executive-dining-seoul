import unittest
from build_official_license_evidence import report

SOURCE={"sha256":"deadbeef","jurisdiction_confirmed_rows":95,"routable_rows":100}
class EvidenceTests(unittest.TestCase):
    def test_never_confirm_spending_from_licence(self):
        d={"sources":[SOURCE],"venues":[
            {"merchant":"A","license_match_status":"EXACT_NAME_AND_ADDRESS","license_name":"A","license_address":"서울 A로 1","license_business_status":"영업"},
            {"merchant":"B","license_match_status":"NAME_AND_BUILDING_ADDRESS_FLOOR_UNVERIFIED","license_name":"B","license_address":"서울 B로 2, 2층"},
            {"merchant":"C","license_match_status":"NOT_MATCHED","official_building_businesses":[{"license_name":"C"}]}]}
        x=report(d)
        self.assertEqual(x["state_counts"],{"OFFICIAL_LICENSE_EXACT_ADDRESS":1,"OFFICIAL_LICENSE_SAME_BUILDING_UNIT_UNVERIFIED":1,"OFFICIAL_LICENSE_IDENTITY_NOT_CONFIRMED":1})
        self.assertTrue(all(not v["payment_branch_verified"] and not v["individual_attendance_verified"] for v in x["venues"]))
        self.assertIsNone(x["venues"][2]["official_licensed_name"])

    def test_no_promotion_without_provenance(self):
        d={"sources":[],"venues":[{"merchant":"A","license_match_status":"EXACT_NAME_AND_ADDRESS","license_name":"A","license_address":"A로 2"}]}
        self.assertEqual(report(d)["venues"][0]["license_evidence_state"],"OFFICIAL_LICENSE_IDENTITY_NOT_CONFIRMED")

if __name__=="__main__":
    unittest.main()
