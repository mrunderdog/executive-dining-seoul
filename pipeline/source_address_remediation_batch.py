"""Rank official original-source document URLs for address-remediation research.

This generates a queue only: source documents are NOT evidence of a venue address
unless their rows explicitly contain an address. No automatic location assignment.
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INPUTS={
 "공기업·공공기관":"public-enterprise-candidates.json",
 "중앙정부":"central-executive-candidates.json",
 "법조·법률행정":"justice-leadership-candidates.json",
}

def build():
    out=[]
    for source,filename in INPUTS.items():
        doc=json.loads((ROOT/"reports"/filename).read_text(encoding="utf-8"))
        by_url=defaultdict(lambda: {"merchants":set(),"institutions":set(),"expense_events":0})
        missing=0
        for cand in doc.get("candidates",[]):
            if str(cand.get("address") or "").strip():continue
            missing+=1
            for rec in cand.get("recent",[]):
                url=str(rec.get("source") or "").strip()
                if not url.startswith("https://"):continue
                b=by_url[url];b["merchants"].add(cand.get("merchant") or "")
                if rec.get("institution"):b["institutions"].add(rec["institution"])
                b["expense_events"]+=1
        rows=[{"url":url,"merchant_count":len(b["merchants"]),
            "institution_count":len(b["institutions"]),"recent_expense_event_references":b["expense_events"],
            "merchant_examples":sorted(b["merchants"])[:8],
            "institution_examples":sorted(b["institutions"])[:8],
            "state":"SOURCE_REVIEW_REQUIRED","verified_address_count":0}
            for url,b in by_url.items()]
        rows.sort(key=lambda a:(-a["merchant_count"],-a["recent_expense_event_references"],a["url"]))
        out.append({"source":source,"candidate_records_missing_address":missing,
            "distinct_official_source_links":len(rows),"priority_source_documents":rows})
    return {"policy":"Source URLs indicate expense evidence only. They are not restaurant-address or card-merchant proof. No auto-enrichment.", "groups":out}

if __name__=="__main__":
    output=ROOT/"reports/source-address-remediation-batch.json"
    output.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps([{"source":x["source"],"missing":x["candidate_records_missing_address"],
        "source_links":x["distinct_official_source_links"]} for x in build()["groups"]],ensure_ascii=False))
