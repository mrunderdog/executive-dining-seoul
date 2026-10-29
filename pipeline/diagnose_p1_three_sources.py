#!/usr/bin/env python3
"""Read-only, source-file-level forensic comparison for Gapyeong/Gimpo/Bupyeong.

Fetches only genuine official attachments from the discovered official post
records, maps rejected rows back to original PDF / Excel table cells, and
compares colliding IDs with the committed baseline. No source file is saved
to data/raw and no QA threshold is changed.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from capital_backfill import canonical_attachment_url
from ingest_council_expense import (fetch_binary, workbook_rows, normalize_sheet,
                                    infer_pdf_context_role, infer_leadership_role,
                                    valid_transaction_merchant, clean_text)
from qa_council_publication import period_bounds

ROOT=Path(__file__).resolve().parents[1]
VALID_SOURCES={"gapyeong","gimpo","bupyeong"}

def cause(row, known_posts, urls):
    err=[]
    try: d=date.fromisoformat(str(row.get("used_date") or ""))
    except ValueError: d=None
    bounds=period_bounds(row.get("source_period"))
    if d is None:err.append("invalid_date")
    elif bounds is None:err.append("invalid_period")
    elif not bounds[0]<=d<=bounds[1]:err.append("date_outside_post_period")
    if not valid_transaction_merchant(row.get("merchant")):err.append("invalid_merchant")
    amount=row.get("amount")
    if not isinstance(amount,(int,float)) or isinstance(amount,bool) or not 0<amount<50_000_000:err.append("amount_missing_or_invalid")
    if row.get("source_post_url") not in known_posts:err.append("post_not_authorized")
    if canonical_attachment_url(row.get("source_attachment_url")) not in urls:err.append("attachment_not_authorized")
    return err

def row_details(row, original):
    idx=row.get("source_row")
    if not isinstance(idx,int):return {}
    left=max(0,idx-2); right=min(len(original),idx+2)
    return {"original_row_index":idx,"original_cells":original[idx-1] if 0<=idx-1<len(original) else None,
            "nearby":[{"index":i+1,"cells":original[i]} for i in range(left,right)]}

def run(source, max_blob_mb):
    root=ROOT/"reports"/"p1-forensics"/source
    root.mkdir(parents=True,exist_ok=True)
    discovery_path=ROOT/"reports"/f"capital-backfill-discovery-{source}.json"
    discovery=json.loads(discovery_path.read_text(encoding="utf-8"))
    posts=[p for p in discovery.get("posts",[]) if p.get("source")==source and p.get("post_url")]
    authorized={canonical_attachment_url(a.get("url")) for p in posts for a in p.get("attachments",[]) if canonical_attachment_url(a.get("url"))}
    known_posts={p["post_url"] for p in posts}
    prior_path=ROOT/"data"/"raw"/f"{source}_expense.json"
    prior=json.loads(prior_path.read_text(encoding="utf-8")) if prior_path.exists() else {}
    prev={r.get("row_id"):r for r in prior.get("rows",[]) if r.get("row_id")}
    prior_file_urls={canonical_attachment_url(f.get("url")) for f in prior.get("files",[]) if canonical_attachment_url(f.get("url"))}
    files=[]; issue_rows=[]; collisions=[]; new_rows=[]; failures=[]; saved=0; samples=[]
    for post in posts:
        for att in post.get("attachments",[]):
            url=att.get("url")
            canonical=canonical_attachment_url(url)
            if not canonical or canonical not in authorized:continue
            if canonical in prior_file_urls:continue  # committed file remains immutable
            name=clean_text(att.get("text")) or urlsplit(url).path.rsplit("/",1)[-1]
            meta={"source":post["source"],"region":post["region"],"jurisdiction":post["jurisdiction"],"institution":post["institution"],
                  "post_url":post["post_url"],"attachment_url":url,"attachment_name":name,"period":post["period"],
                  "default_role":infer_leadership_role(name) or infer_leadership_role(post["title"])}
            item={"url":url,"post_url":post["post_url"],"title":post.get("title"),
                  "period":post.get("period"),"name":name,"sheets":[]}
            print("FILE",source,url,flush=True)
            try:
                blob=fetch_binary(url,post["post_url"])
                item["sha256"]=hashlib.sha256(blob).hexdigest()
                item["bytes"]=len(blob)
                carried=""
                for sheet,table in workbook_rows(blob,name):
                    page=infer_pdf_context_role(table) if sheet.startswith("pdf-page-") else ""
                    if page:carried=page
                    meta["default_role"]=page or carried or infer_leadership_role(name) or infer_leadership_role(post["title"])
                    normalized,info=normalize_sheet(table,sheet,meta)
                    item["sheets"].append({"sheet":sheet,"header_mapping":info.get("mapping"),"status":info.get("status"),
                                           "parsed_rows":len(normalized),"header_row":info.get("header_row"),
                                           "table_preview":table[:8]})
                    for row in normalized:
                        rid=row["row_id"]
                        if rid in prev:
                            if row!=prev[rid]:
                                conflict={"row_id":rid,"old":prev[rid],"reparsed":row,
                                          "same_url":canonical_attachment_url(prev[rid].get("source_attachment_url"))==canonical,
                                          "original":row_details(row,table)}
                                collisions.append(conflict)
                        else:new_rows.append(row)
                        bad=cause(row,known_posts,authorized)
                        if bad:
                            issue={"reasons":bad,"row":row,"original":row_details(row,table)}
                            issue_rows.append(issue)
                    if len(samples)<70 and source=="gimpo":
                        if any("date_outside_post_period" in cause(r,known_posts,authorized)
                               for r in normalized):
                            samples.append({"sheet":sheet,"source_url":url,"header":table[:9],
                                "bad_example":[{"row":r,"original":row_details(r,table)} for r in normalized
                                               if "date_outside_post_period" in cause(r,known_posts,authorized)][:5]})
                if ((source=="gapyeong" and any(x["row"]["source_attachment_url"]==url for x in issue_rows))
                    or (source=="gimpo" and any(x["row"]["source_attachment_url"]==url for x in issue_rows))
                    or (source=="bupyeong" and any(x["reparsed"]["source_attachment_url"]==url for x in collisions))
                   ) and len(blob)<max_blob_mb*1024*1024 and saved<4:
                    ext=".pdf" if blob.startswith(b"%PDF") else ".xlsx" if blob.startswith(b"PK") else ".xls" if blob.startswith(bytes.fromhex("D0CF11E0A1B11AE1")) else ".bin"
                    target=root/f"official-{saved+1}{ext}"
                    target.write_bytes(blob)
                    item["saved_official_copy"]=target.name
                    saved+=1
            except Exception as e:
                failures.append({"url":url,"error":f"{type(e).__name__}: {e}"})
            files.append(item)
    reasons=Counter(y for x in issue_rows for y in x["reasons"])
    report={"source":source,"baseline_rows":len(prev),"baseline_files":len(prior_file_urls),
            "official_posts":len(posts),"official_attachments":len(authorized),"new_attachment_count":len(files),
            "download_errors":failures,"new_rows":len(new_rows),"collisions":len(collisions),
            "invalid_rows":len(issue_rows),"invalid_reason_counts":dict(reasons),
            "files":files,"issues":issue_rows[:90],"collision_details":collisions[:30],
            "out_of_period_sheets":samples[:40]}
    (root/"forensics.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    print("FORENSICS",json.dumps({k:report[k] for k in ("source","baseline_rows","official_posts","official_attachments","new_attachment_count","new_rows","collisions","invalid_rows","invalid_reason_counts","download_errors")},ensure_ascii=False),flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True,choices=sorted(VALID_SOURCES))
    ap.add_argument("--max-blob-mb",type=int,default=9)
    args=ap.parse_args()
    run(args.source,args.max_blob_mb)
