"""Synthetic contract tests for SHA-attested historical metadata (not source proof)."""
import copy
import json
import unittest
from pathlib import Path

from incheon_reparse_attestation import (
    attest_legacy_files,make_attested_qa_view,LEGACY_SEQUENCES,
)

ROOT=Path(__file__).resolve().parents[1]

def fixture():
    baseline=json.loads((ROOT/"data/raw/incheon_council_expense.json").read_text(encoding="utf-8"))
    reference=json.loads((ROOT/"pipeline/incheon_official_2026_08_09_text_evidence.json").read_text(encoding="utf-8"))
    d={}
    for expected in reference["files"]:
        seq=expected["msg_seq"]
        if seq not in LEGACY_SEQUENCES:continue
        file=next(x for x in baseline["files"] if f"msg_seq={seq}" in x["url"])
        page_counts=[15,5] if seq==1320 else [expected["transactions"]]
        pages=[]
        for i,n in enumerate(page_counts,1):
            pages.append({"sheet":f"pdf-page-{i}","normalized_count":n,
                          "current_parser":{"sheet":f"pdf-page-{i}","status":"OK",
                              "parsed_rows":n,"unparsed_transaction_like_rows":0}})
        # Synthetic source rows only validate the trust contract / accounting.
        amounts=[1]*(expected["transactions"]-1)
        amounts.append(expected["amount_total_krw"]-sum(amounts))
        d[seq]={"msg_seq":seq,"url":file["url"],"sha256":file["sha256"],
                "bytes":file["bytes"],"pdf_page_count":expected["pages"],
                "pages":pages,"exceptions":[],
                "staged_full_rows":[{"row_id":f"test-{seq}-{i}","amount":amount}
                                    for i,amount in enumerate(amounts)]}
    return baseline,reference,{"documents":list(d.values())}


class HistoricalAttestationTests(unittest.TestCase):
    def test_verified_shadow_does_not_mutate_history(self):
        old,original,forensic=fixture()
        saved=copy.deepcopy(old)
        proof,shadow=attest_legacy_files(old,forensic,original)
        self.assertEqual(proof["status"],"PASS",proof)
        self.assertEqual(proof["attested_files"],5)
        self.assertEqual(proof["total_attested_transactions"],58)
        proposed={**old,"rows":[*old["rows"],{"row_id":"new-stage"}]}
        pristine=copy.deepcopy(proposed)
        view=make_attested_qa_view(proposed,shadow,proof)
        self.assertEqual(old,saved)
        self.assertEqual(proposed,pristine)
        self.assertEqual(len(view["files"]),10)
        self.assertTrue(all(f["sheets"][0]["status"]=="NO_HEADER"
                            for f in proposed["files"] if f["url"] in shadow))
        self.assertTrue(all(f["sheets"][0]["status"]=="OK"
                            for f in view["files"] if f["url"] in shadow))

    def test_changed_original_pdf_sha_holds(self):
        old,expected,data=fixture()
        data["documents"][0]["sha256"]="0"*64
        proof,shadow=attest_legacy_files(old,data,expected)
        self.assertEqual(proof["status"],"HOLD")
        self.assertEqual(shadow,{})
        with self.assertRaises(ValueError):
            make_attested_qa_view(old,shadow,proof)

    def test_unparsed_transaction_page_holds(self):
        old,expected,data=fixture()
        doc=next(d for d in data["documents"] if d["msg_seq"]==1320)
        doc["pages"][1]["current_parser"]["status"]="ROW_PARSE_GAPS"
        doc["pages"][1]["current_parser"]["unparsed_transaction_like_rows"]=1
        proof,shadow=attest_legacy_files(old,data,expected)
        self.assertEqual(proof["status"],"HOLD",proof)
        self.assertEqual(shadow,{})

    def test_missing_fifth_verified_pdf_holds(self):
        old,expected,data=fixture()
        data["documents"]=data["documents"][:-1]
        proof,shadow=attest_legacy_files(old,data,expected)
        self.assertEqual(proof["status"],"HOLD")
        self.assertEqual(shadow,{})

    def test_unrecognized_original_sheet_status_holds(self):
        old,expected,data=fixture()
        changed=copy.deepcopy(old)
        file=next(x for x in changed["files"] if "msg_seq=1326" in x["url"])
        file["sheets"][0]["status"]="OK"
        proof,shadow=attest_legacy_files(changed,data,expected)
        self.assertEqual(proof["status"],"HOLD")
        self.assertEqual(shadow,{})


if __name__=="__main__":
    unittest.main()
