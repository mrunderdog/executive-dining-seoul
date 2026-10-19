import csv
import tempfile
import unittest
from pathlib import Path
from audit_three_unresolved_venues import check_cafe_file, check_three

class CafeEvidenceTest(unittest.TestCase):
    def test_official_cafe_name_and_building(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"source.csv"
            with p.open("w",encoding="utf-8",newline="") as f:
                w=csv.DictWriter(f,fieldnames=["사업장명","도로명전체주소","영업상태명","인허가일자"])
                w.writeheader()
                w.writerow({"사업장명":"빈티지204","도로명전체주소":"서울특별시 은평구 은평로 193-1, 1층","영업상태명":"영업/정상","인허가일자":"2021-01-01"})
                w.writerow({"사업장명":"타카페","도로명전체주소":"서울특별시 은평구 은평로 193-1, 2층","영업상태명":"영업/정상"})
            r=check_cafe_file(p)
            self.assertEqual(r["status"],"OFFICIAL_REST_CAFE_NAME_AND_BUILDING_MATCH")
            self.assertEqual(r["same_name_same_building_count"],1)

    def test_cross_region_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"source.csv"
            p.write_text("사업장명,도로명전체주소\n빈티지204,서울특별시 종로구 종로 1\n",encoding="utf-8")
            with self.assertRaises(ValueError):check_cafe_file(p)

if __name__=="__main__":unittest.main()
