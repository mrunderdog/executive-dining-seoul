"""Regression checks for evidence attribution and offline official-license lookups."""
import unittest
from audit_restaurant_licenses import evaluate, load_official
from evidence_semantics import classify_record,apply_evidence_semantics

class EvidenceSemanticsTests(unittest.TestCase):
    def test_expense_record_does_not_become_personal_visit(self):
        record={"name":"테스트","evidence":{"visits":5,"spending_events":0}}
        x=classify_record(record)
        self.assertEqual(x["reported_usage_events"],5)
        self.assertEqual(x["confirmed_person_attendances"],0)
        self.assertEqual(x["personal_attendance_status"],"NOT_ESTABLISHED")
    def test_police_spend_separate(self):
        x=classify_record({"evidence":{"visits":0,"spending_events":3}})
        self.assertEqual(x["disclosed_spending_events"],3)
        self.assertEqual(x["confirmed_person_attendances"],0)
    def test_all_records_annotated(self):
        d=apply_evidence_semantics({"records":[{"evidence":{"visits":2}}]})
        self.assertEqual(d["records"][0]["evidence_semantics"]["reported_usage_events"],2)
    def test_license_match_does_not_certify_card_or_attendee(self):
        v=[{"merchant":"소담","address":"서울특별시 중구 세종대로 12"}]
        raw=[{"사업장명":"소담","도로명전체주소":"서울특별시 중구 세종대로 12","영업상태명":"영업"}]
        x=evaluate(v,raw)[0]
        self.assertEqual(x["license_match_status"],"EXACT_NAME_AND_ADDRESS")
        self.assertFalse(x["payment_branch_verified"])
        self.assertFalse(x["personal_attendance_verified"])
    def test_duplicate_or_wrong_address_held(self):
        v=[{"merchant":"소담","address":"서울특별시 중구 세종대로 12"}]
        raw=[{"사업장명":"소담","도로명전체주소":"서울특별시 중구 세종대로 12"}]*2
        self.assertEqual(evaluate(v,raw)[0]["license_match_status"],"AMBIGUOUS_LICENSE_RECORDS")
        self.assertEqual(evaluate(v,[{"사업장명":"소담","도로명전체주소":"서울특별시 중구 세종대로 15"}])[0]["license_match_status"],"NOT_MATCHED")
if __name__=="__main__":unittest.main()
