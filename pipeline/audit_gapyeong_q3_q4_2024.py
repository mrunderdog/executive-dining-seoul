#!/usr/bin/env python3
"""Read-only exact original PDF comparison for Gapyeong 2024 Q3/Q4.

Never reassign a document quarter or forge dates. Compare economic records
across two independently authorized official PDFs. Match source-row identity
only when date,time,role,merchant,purpose,amount,attendees,payment all agree.
"""
from __future__ import annotations
import json,hashlib,sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from capital_backfill import SOURCES,discover_source,canonical_attachment_url
from ingest_council_expense import (fetch_binary,workbook_rows,normalize_sheet,
    infer_pdf_context_role,infer_leadership_role)
from qa_council_publication import period_bounds
from reconcile_gimpo_sources import economic_key,within_declared_period

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports"/"gapyeong-2024-cross-quarter"
OUT.mkdir(parents=True,exist_ok=True)
src=replace(next(s for s in SOURCES if s.key=="gapyeong"),max_pages=1)
posts=discover_source(src,(2024,7),(2024,12))
errors=[p for p in posts if p.get("error")]
selected={}
for p in posts:
    if p.get("period") in ((2024,None,3),(2024,None,4)):
        q=p["period"][2]
        if q in selected:
            raise RuntimeError("duplicate official post for quarter "+str(q))
        selected[q]=p
if sorted(selected)!=[3,4]:
    raise RuntimeError("official Q3/Q4 posts not both discovered: "+str([(p.get('title'),p.get('error')) for p in posts]))
if errors: raise RuntimeError("partial discovery: "+str(errors))
all_rows={}
files={}
for quarter,post in selected.items():
    attachments=post.get("attachments") or []
    if len(attachments)!=1:raise RuntimeError(f"Q{quarter} expected single original PDF, got {len(attachments)}")
    a=attachments[0]
    url=a.get("url")
    if not canonical_attachment_url(url) or "gpassem.go.kr" not in url:
        raise RuntimeError("not an authorized official attachment: "+str(url))
    print(f"OFFICIAL Q{quarter} post={post['post_url']} attachment={url}",flush=True)
    blob=fetch_binary(url,post["post_url"])
    if not blob.startswith(b"%PDF"):raise RuntimeError("attachment is not PDF")
    digest=hashlib.sha256(blob).hexdigest()
    # Q4 hash was previously independently preserved and inspected.
    known_original_digests = {
        3: "b58beb42faee678e3a514629a5c87371b0fda62eec783371d80d458bee6da5d1",
        4: "b542fd71e914c9d6e9302ee3fa00b49f86edefcb8a4504768eb127dc310875a1",
    }
    if digest != known_original_digests[quarter]:
        raise RuntimeError(f"Q{quarter} original official PDF hash changed since independently verified audit")
    records=[]
    sheets=[]
    carried=""
    for sheet,source_rows in workbook_rows(blob,"verified-official.pdf"):
        role=infer_pdf_context_role(source_rows)
        if role:carried=role
        meta={"source":"gapyeong","region":"경기","jurisdiction":"가평군",
              "institution":"가평군의회","post_url":post["post_url"],
              "attachment_url":url,"attachment_name":a.get("text") or "verified-official.pdf",
              "period":post["period"],"attachment_sha256":digest,
              "default_role":role or carried or infer_leadership_role(a.get("text",""))}
        rows,info=normalize_sheet(source_rows,sheet,meta)
        sheets.append(info)
        records.extend(rows)
    if any(s.get("unparsed_transaction_like_rows") for s in sheets):
        raise RuntimeError("original PDF still has unparsed numbered expense records")
    all_rows[quarter]=records
    files[quarter]={"sha256":digest,"bytes":len(blob),"url":url,
                    "post":post["post_url"],"title":post["title"],
                    "rows":len(records),"sheets":sheets}
    print(f"Q{quarter} parsed={len(records)} sha={digest}",flush=True)

q3,q4=all_rows[3],all_rows[4]
q3_index=defaultdict(list);q4_index=defaultdict(list)
for r in q3:q3_index[economic_key(r)].append(r)
for r in q4:q4_index[economic_key(r)].append(r)
issues=[];matched=[];counts=Counter()
def do_compare(source_quarter,target_quarter):
    source=all_rows[source_quarter]
    target_index=q4_index if target_quarter==4 else q3_index
    source_mismatch=[r for r in source if not within_declared_period(r)]
    for r in source_mismatch:
        others=[t for t in target_index.get(economic_key(r),[])
                if within_declared_period(t)
                and t.get("source_attachment_url")!=r.get("source_attachment_url")]
        evidence={"printed_date":r.get("used_date"),"used_time":r.get("used_time"),
                  "role":r.get("role"),"merchant":r.get("merchant"),
                  "amount":r.get("amount"),"purpose":r.get("purpose"),
                  "people":r.get("people"),"payment_method":r.get("payment_method"),
                  "source_quarter":source_quarter,
                  "source_file_url":r.get("source_attachment_url"),
                  "source_post_url":r.get("source_post_url"),
                  "source_sheet":r.get("source_sheet"),"source_row":r.get("source_row"),
                  "matches_in_target_quarter":len(others)}
        if len(others)==1:
            t=others[0]
            evidence["matched_in_period"]={
                "quarter":target_quarter,"source_file_url":t["source_attachment_url"],
                "source_post_url":t["source_post_url"],
                "source_sheet":t["source_sheet"],"source_row":t["source_row"],
                "row_id":t["row_id"]}
            evidence["disposition"]="EXACT_IN_PERIOD_CROSS_FILE_DUPLICATE"
            matched.append(evidence)
        else:
            evidence["disposition"]="HOLD_PERIOD_AMBIGUITY"
            # Report nearest candidates using date+time+amount to expose small
            # differences without assuming two records are the same.
            near=[t for t in all_rows[target_quarter]
                  if (t.get("used_date"),t.get("used_time"),t.get("amount"))==
                     (r.get("used_date"),r.get("used_time"),r.get("amount"))]
            evidence["near_source_examples"]=[{
                "merchant":t.get("merchant"),"purpose":t.get("purpose"),
                "role":t.get("role"),"source_row":t.get("source_row"),
                "source_sheet":t.get("source_sheet"),
                "attendees":t.get("people"),"payment_method":t.get("payment_method")
                } for t in near[:4]]
            issues.append(evidence)
        counts[f"Q{source_quarter}_outside_period"]+=1
        counts[evidence["disposition"]]+=1
do_compare(3,4);do_compare(4,3)
all_valid=[]
for quarter,rows in all_rows.items():
    all_valid.extend(r for r in rows if within_declared_period(r))
keys=[economic_key(r) for r in all_valid]
valid_dups=len(keys)-len(set(keys))
out={"status":"ALL_MISMATCHES_MATCHED" if not issues else "HOLD",
     "files":files,"counts":dict(counts),
     "q3_rows":len(q3),"q4_rows":len(q4),
     "q3_in_period_rows":sum(within_declared_period(x) for x in q3),
     "q4_in_period_rows":sum(within_declared_period(x) for x in q4),
     "in_period_economic_identity_duplicates":valid_dups,
     "exact_match_evidence":matched,
     "unresolved_mismatch_evidence":issues,
     "unknown_discovery_errors":errors,
     "policy":"No source-period relabeling; only exact matches to independently official in-period rows can support deduplication."}
p=OUT/"comparison.json"
p.write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
text=["# Gapyeong Q3–Q4 2024 actual official PDF reconciliation",
      "","- Q3 PDF SHA-256: "+files[3]["sha256"],
      "- Q4 PDF SHA-256: "+files[4]["sha256"],
      "- Q3 source rows: "+str(len(q3))+"; Q4 source rows: "+str(len(q4)),
      "- Official source out-of-quarter Q3: "+str(counts["Q3_outside_period"])+"; Q4: "+str(counts["Q4_outside_period"]),
      "- Exact cross-document in-period matches: "+str(len(matched)),
      "- Unresolved official mismatches: "+str(len(issues)),
      "- Exact in-period duplicates: "+str(valid_dups),
      "- Audit status: "+out["status"],"",
      "## Unresolved rows",""]
for x in issues:text.append(f"- {x['printed_date']} {x['used_time']} {x['merchant']} ₩{x['amount']} source Q{x['source_quarter']} near matches: {x['near_source_examples']}")
text.extend(["","## Exact cross-quarter matched rows",""])
for x in matched:text.append(f"- {x['printed_date']} {x['used_time']} {x['merchant']} ₩{x['amount']} source Q{x['source_quarter']} -> Q{x['matched_in_period']['quarter']}, PDF rows {x['source_row']} -> {x['matched_in_period']['source_row']}")
(OUT/"comparison.md").write_text("\n".join(text)+"\n",encoding="utf-8")
print(json.dumps({k:out[k] for k in ("status","counts","q3_rows","q4_rows","q3_in_period_rows","q4_in_period_rows","in_period_economic_identity_duplicates")},ensure_ascii=False,indent=2),flush=True)
# Audit completion is distinct from publication approval. The conflicting
# official payment method must remain HOLD and cannot be deduplicated merely
# by merchant/date/amount.
expected=(len(q3)==45 and len(q4)==103
          and counts["Q3_outside_period"]==1
          and counts["Q4_outside_period"]==19
          and len(matched)==19 and len(issues)==1)
if not expected:
    raise SystemExit("Unexpected source or reconciliation drift; no publication")
issue=issues[0]
if not (issue["printed_date"]=="2024-09-13"
        and issue["used_time"]=="13:00"
        and issue["merchant"]=="영남농원"
        and issue["amount"]==1650000
        and len(issue["near_source_examples"])==1
        and issue["payment_method"]=="신용카드"
        and issue["near_source_examples"][0]["payment_method"]=="계좌이체"):
    raise SystemExit("Unrecognized original payment-method mismatch; no publication")
print("AUDIT_COMPLETE_WITH_HELD_CONFLICT; NOT_PUBLICATION_READY",flush=True)
