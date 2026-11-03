#!/usr/bin/env python3
"""Stage five SHA-verified Incheon Council PDF files; NEVER publish.

Reparse only five pre-existing committed files in which old ingestion
recorded NO_HEADER, while preserving all baseline records and file metadata.
The scanned 1321 PDF and other unresolved official files are explicitly NOT
covered; stage success must not be treated as complete source publication.
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"pipeline"))
from capital_backfill import canonical_attachment_url
from ingest_council_expense import fetch_binary,workbook_rows,normalize_sheet
from incheon_verified_pdf import VERIFIED
from qa_council_publication import git_json,assess_incremental
from guard_full_council import check_integrity

def main():
    source="incheon_council"
    raw_path=ROOT/"data/raw/incheon_council_expense.json"
    discover_path=ROOT/"reports/capital-backfill-discovery-incheon_council.json"
    baseline=git_json("HEAD","data/raw/incheon_council_expense.json")
    baseline_disc=git_json("HEAD","reports/capital-backfill-discovery-incheon_council.json")
    if not baseline or not baseline_disc:
        raise SystemExit("HOLD: missing committed source baseline")
    current=json.loads(raw_path.read_text(encoding="utf-8"))
    discovery=json.loads(discover_path.read_text(encoding="utf-8"))
    oldrows={r.get("row_id"):r for r in baseline.get("rows",[])}
    nowrows={r.get("row_id"):r for r in current.get("rows",[])}
    if len(oldrows)!=len(baseline.get("rows",[])) or any(nowrows.get(k)!=v for k,v in oldrows.items()):
        raise SystemExit("HOLD: baseline rows not preserved")
    if current.get("files") != baseline.get("files"):
        raise SystemExit("HOLD: initial attachment inventory not identical to baseline")
    oldfiles={canonical_attachment_url(x.get("url")):x for x in baseline.get("files",[])}
    all_rows=[]
    proof=[]
    for sha,(seq,month,role,expected_pages) in VERIFIED.items():
        filename_url=f"https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&fileno=1&msg_seq={seq}"
        canon=canonical_attachment_url(filename_url)
        old=oldfiles.get(canon)
        if not old or old.get("sha256")!=sha:
            raise SystemExit(f"HOLD: original file SHA/inventory mismatch {seq}")
        if any(x.get("status")!="NO_HEADER" or x.get("parsed_rows") for x in old.get("sheets",[])):
            raise SystemExit(f"HOLD: {seq} was not an original zero-parsed source")
        owners=[p for p in baseline_disc.get("posts",[]) if p.get("source")==source
                and any(canonical_attachment_url(a.get("url"))==canon for a in p.get("attachments",[]))]
        if not owners:
            raise SystemExit(f"HOLD: no verified official discovery link for {seq}")
        # The public listing contains exact observed file links. Do not invent
        # a post URL when the detail page was previously unreachable.
        owner=next((p for p in owners if "bbsMsgDetail.do" in p.get("post_url","")), owners[0])
        if owner.get("period") != [2026,month,None]:
            raise SystemExit(f"HOLD: official reporting month mismatch {seq}")
        blob=fetch_binary(filename_url,owner["post_url"])
        actualsha=hashlib.sha256(blob).hexdigest()
        if actualsha!=sha or not blob.startswith(b"%PDF"):
            raise SystemExit(f"HOLD: original PDF changed or invalid {seq}")
        meta={"source":source,"region":"인천","jurisdiction":"인천광역시",
              "institution":"인천광역시의회","post_url":owner["post_url"],
              "attachment_url":filename_url,"attachment_name":old.get("name",""),
              "attachment_sha256":sha,"period":owner["period"],"default_role":role}
        sections,parsed={},[]
        for sheet,rows in workbook_rows(blob,old.get("name") or f"{seq}.pdf"):
            found,info=normalize_sheet(rows,sheet,meta)
            sections[sheet]=info
            if info.get("status")!="OK":
                raise SystemExit(f"HOLD: incomplete official source {seq}/{sheet}: {info}")
            parsed.extend(found)
        if {k:v.get("parsed_rows") for k,v in sections.items()} != expected_pages:
            raise SystemExit(f"HOLD: official page/transaction mismatch {seq}")
        if any(x["row_id"] in oldrows for x in parsed):
            raise SystemExit(f"HOLD: historical transaction ID collision {seq}")
        all_rows.extend(parsed)
        proof.append({"seq":seq,"sha256":sha,"month":month,"file":filename_url,
                      "post":owner["post_url"],"pages":sections,"recovered_rows":len(parsed)})
    if len(all_rows)!=58 or len({r["row_id"] for r in all_rows})!=58:
        raise SystemExit("HOLD: 58 expected distinct transaction records not recovered")
    candidate={**current,"rows":sorted([*current["rows"],*all_rows],
                key=lambda x:(x.get("used_date",""),x.get("row_id","")))}
    candidate["row_count"]=len(candidate["rows"])
    integrity=check_integrity(source,candidate,baseline)
    qa=assess_incremental(source,candidate,discovery,baseline,baseline_disc)
    if integrity.get("status")!="PASS" or qa.get("status")!="PUBLISH_READY":
        raise SystemExit(f"HOLD: strict QA/integrity rejected verified recovery: {qa}, {integrity}")
    evidence={"source":source,"status":"PARTIAL_STAGED_ONLY_NOT_PUBLISHED",
              "baseline_rows":len(oldrows),"recovered_rows":len(all_rows),
              "candidate_rows":len(candidate["rows"]),"original_files_unchanged":len(oldfiles),
              "scope_exclusions":["scanned official 1321 PDF","unresolved null amount row e6256a2ab172f5fd2ac7",
                                  "all other not-yet-accounted official attachments"],
              "proof":proof,"qa":qa,"integrity":integrity}
    dest=ROOT/"reports/recovery/incheon-verified-partial-backfill.json"
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":evidence["status"],"baseline":len(oldrows),
                      "recovered":len(all_rows),"candidate":len(candidate["rows"]),
                      "qa":qa["status"],"integrity":integrity["status"]},ensure_ascii=False))
    # Intentional: do not write candidate to source JSON; this is a read-only
    # proof, and release remains blocked until scanned/invalid files are fixed.

if __name__=="__main__":
    main()
