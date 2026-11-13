#!/usr/bin/env python3
"""One-shot release review for two independently reconciled official sources.

Only audited and fully accounted *valid* original expense rows are permitted
into the financial ledger. All 11 unresolved original records remain visible
in source_recovery, but no guessed record, restaurant ranking or site change
may be committed. The separate CI must also validate rendered HTML.
"""
from __future__ import annotations
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

from capital_backfill import canonical_attachment_url
from guard_full_council import check_discovery,check_integrity
from qa_council_publication import assess_incremental
from build_source_candidates import build_candidates

ROOT=Path(__file__).resolve().parents[1]
SPECS={
    "ansan":{"before_rows":658,"before_files":2,
             "after_rows":2991,"after_files":8,
             "new_rows":2333,"full_original_new_rows":2336,
             "excluded_count":3,"excluded_amount":497200},
    "hwaseong":{"before_rows":840,"before_files":4,
                "after_rows":4073,"after_files":23,
                "new_rows":3233,"full_original_new_rows":3241,
                "excluded_count":8,"excluded_amount":1989620},
}
EXPECTED_BOTH_VALID=5566
EXPECTED_BOTH_HELD=11
EXPECTED_BOTH_VALID_AMOUNT=891870199


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stable_sha(obj):
    return sha(json.dumps(obj,ensure_ascii=False,sort_keys=True).encode("utf-8"))


def fail(msg):
    raise ValueError("BLOCK SOURCE PUBLICATION: "+msg)


def validate():
    root=Path(os.environ["RUNNER_TEMP"])/"p1-release"
    baselines={}
    proposed={}
    written=[]
    ranks_before={s:build_candidates(s)[1] for s in SPECS}
    candidate_bytes={s:(ROOT/f"reports/{s}-executive-candidates.json").read_bytes() for s in SPECS}
    for source,spec in SPECS.items():
        origin=ROOT/f"data/raw/{source}_expense.json"
        discpath=ROOT/f"reports/capital-backfill-discovery-{source}.json"
        old_bytes=origin.read_bytes()
        origdisc_bytes=discpath.read_bytes()
        old=json.loads(old_bytes)
        olddisc=json.loads(origdisc_bytes)
        folder=root/source
        next_data=read(folder/f"{source}-source-only-candidate.json")
        next_disc=read(folder/f"{source}-discovery-candidate.json")
        policy_exc=read(folder/f"{source}-source-exceptions.json")
        manifest=read(folder/f"{source}-subset-manifest.json")
        if stable_sha(old)!=manifest.get("baseline_source_sha256"):
            fail(f"{source} previously approved source baseline SHA changed")
        if stable_sha(olddisc)!=manifest.get("baseline_discovery_sha256"):
            fail(f"{source} previous official discovery SHA changed")
        if stable_sha(next_data)!=manifest.get("source_candidate_sha256"):
            fail(f"{source} candidate artifact SHA mismatch")
        if stable_sha(next_disc)!=manifest.get("discovery_candidate_sha256"):
            fail(f"{source} official discovery snapshot SHA mismatch")
        if (manifest.get("source")!=source
            or manifest.get("status")!="PARTIAL_SOURCE_ONLY_REVIEWABLE"
            or manifest.get("strict_qa")!="PUBLISH_READY"
            or manifest.get("verified_rows")!=spec["new_rows"]
            or manifest.get("integrity")!="PASS"
            or manifest.get("discovery")!="PASS"
            or manifest.get("ranking_changes")!=0
            or manifest.get("historical_rows_modified")!=0
            or manifest.get("historical_files_modified")!=0
            or manifest.get("full_source_complete") is not False
            or manifest.get("publish") is not False
            or manifest.get("approved_to_merge") is not False):
            fail(source+" unapproved or incomplete audit")
        if (len(old.get("rows",[]))!=spec["before_rows"]
            or len(old.get("files",[]))!=spec["before_files"]
            or len(next_data.get("rows",[]))!=spec["after_rows"]
            or len(next_data.get("files",[]))!=spec["after_files"]
            or next_data["rows"][:spec["before_rows"]]!=old["rows"]
            or next_data["files"][:spec["before_files"]]!=old["files"]
            or next_data.get("errors")!=old.get("errors")):
            fail(source+" immutable historical financial source changed")
        current=next_data["source_recovery"]
        if (current.get("source_status")!="PARTIAL_EXPENSE_SOURCE_ONLY_WITH_EXPLICIT_EXCEPTIONS"
            or current.get("official_source_completeness")!="HOLD_UNRESOLVED_ORIGINAL_ROWS"
            or current.get("ranking_eligible") is not False
            or current.get("whole_disclosure_reconciled") is not False
            or current.get("new_source_verified_unranked")!=spec["new_rows"]
            or current.get("original_rows_parsed")!=spec["full_original_new_rows"]
            or current.get("original_exceptions_count")!=spec["excluded_count"]
            or current.get("original_exceptions_total_krw")!=spec["excluded_amount"]
            or current.get("unresolved_original_expense_rows")!=policy_exc):
            fail(source+" unresolved original exception ledger missing or modified")
        if len(policy_exc)!=spec["excluded_count"]:
            fail(source+" exception count inconsistent")
        ids_old={r["row_id"] for r in old["rows"]}
        new_rows=next_data["rows"][spec["before_rows"]:]
        if (len(new_rows)!=spec["new_rows"]
            or len({x["row_id"] for x in new_rows})!=len(new_rows)
            or ids_old.intersection({x["row_id"] for x in new_rows})):
            fail(source+" missing or duplicate new source transaction IDs")
        if any(r.get("date_quality")!="source_verified_unranked"
               or r.get("ranking_eligible") is not False
               or r.get("recommendation_status")!="HOLD_PAYMENT_BRANCH_UNVERIFIED"
               for r in new_rows):
            fail(source+" unverified expense eligible for site ranking")
        if len(next_data["files"])!=len({canonical_attachment_url(f["url"])
                                        for f in next_data["files"]}):
            fail(source+" duplicate official file URL")
        files={canonical_attachment_url(f["url"]):f
               for f in next_data["files"]}
        for exception in policy_exc:
            u=canonical_attachment_url(exception["official_attachment_url"])
            if (exception.get("status")!="HOLD_ORIGINAL_UNRESOLVED"
                or exception.get("included_in_verified_source_rows") is not False
                or exception.get("included_in_restaurant_rankings") is not False
                or exception.get("row_id") in ids_old
                or exception.get("row_id") in {r["row_id"] for r in new_rows}
                or u not in files or files[u]["sha256"]!=exception["file_sha256"]
                or not isinstance(exception.get("exact_source_cells"),list)):
                fail(source+" one historical source exception was concealed or changed")
        if (len({x["row_id"] for x in policy_exc})!=len(policy_exc)
            or sum(x["amount"] for x in policy_exc)!=spec["excluded_amount"]):
            fail(source+" original exception monetary inventory incomplete")
        new_amount=sum(r["amount"] for r in new_rows)
        if current["new_verified_row_total_krw"]!=new_amount:
            fail(source+" accepted official source amount changed")
        if (next_data.get("row_count")!=spec["after_rows"]
            or next_data.get("raw_quality",{}).get("rows")!=spec["after_rows"]
            or next_data.get("raw_quality",{}).get("in_period_date_coverage")!=1.0):
            fail(source+" partial source reporting not updated")
        baseline_posts={p["post_url"]:p for p in olddisc.get("posts",[])}
        after_posts={p["post_url"]:p for p in next_disc.get("posts",[])}
        if any(after_posts.get(url)!=p for url,p in baseline_posts.items()):
            fail(source+" historical official posts changed")
        if len(after_posts)!=len(next_disc.get("posts",[])):
            fail(source+" duplicate official discovery post IDs")
        integrity=check_integrity(source,next_data,old)
        qa=assess_incremental(source,next_data,next_disc,old,olddisc)
        discovery_guard=check_discovery(source,next_disc,old)
        if (integrity["status"]!="PASS"
            or qa["status"]!="PUBLISH_READY"
            or qa.get("verified_rows")!=spec["new_rows"]
            or discovery_guard["status"]!="PASS"):
            fail(source+" independent release strict QA/integrity failed "+str({
                "source_qa":qa,"integrity":integrity,"discovery":discovery_guard}))
        baselines[source]=(old_bytes,origdisc_bytes)
        proposed[source]=(next_data,next_disc)
        print(json.dumps({
            "source":source,"stage":"SHA_PRESERVING_RELEASE_REVIEW_PASS",
            "new_rows":len(new_rows),"new_amount_krw":new_amount,
            "unresolved_rows":len(policy_exc),
            "strict_qa":qa["status"],"integrity":integrity["status"],
            "new_rankings":0,"complete_source":False,
        },ensure_ascii=False),flush=True)
    if sum(x["new_source_verified_unranked"] for x,d in
           [(r[0]["source_recovery"],r[1]) for r in proposed.values()])!=EXPECTED_BOTH_VALID:
        fail("sum of both source reviewed rows changed")
    if sum(len(p[0]["source_recovery"]["unresolved_original_expense_rows"])
           for p in proposed.values())!=EXPECTED_BOTH_HELD:
        fail("missing original financial exceptions")
    if sum(p[0]["source_recovery"]["new_verified_row_total_krw"]
           for p in proposed.values())!=EXPECTED_BOTH_VALID_AMOUNT:
        fail("independently reviewed accepted expenses total changed")
    try:
        for source,(next_data,next_disc) in proposed.items():
            rawfile=ROOT/f"data/raw/{source}_expense.json"
            discfile=ROOT/f"reports/capital-backfill-discovery-{source}.json"
            rawfile.write_text(json.dumps(next_data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            discfile.write_text(json.dumps(next_disc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            written.append(source)
        for source in SPECS:
            rank_after=build_candidates(source)[1]
            if (ranks_before[source]!=rank_after
                or candidate_bytes[source]!=(ROOT/f"reports/{source}-executive-candidates.json").read_bytes()):
                fail(source+" existing rank/candidate contents changed")
    except Exception:
        for source in written:
            old_bytes,old_disc=baselines[source]
            (ROOT/f"data/raw/{source}_expense.json").write_bytes(old_bytes)
            (ROOT/f"reports/capital-backfill-discovery-{source}.json").write_bytes(old_disc)
        raise
    print(json.dumps({"status":"BOTH_PARTIAL_SOURCE_STAGED",
                      "new_valid_source_rows":EXPECTED_BOTH_VALID,
                      "source_amount_krw":EXPECTED_BOTH_VALID_AMOUNT,
                      "separate_held_original_rows":EXPECTED_BOTH_HELD,
                      "new_rankings":0,"public_site_checked_later":True},ensure_ascii=False))


if __name__=="__main__":
    validate()
