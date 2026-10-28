#!/usr/bin/env python3
"""Non-publishing audit of Icheon official attachment discovery and raw row lineage."""
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path
from capital_backfill import canonical_attachment_url

ROOT=Path(__file__).resolve().parents[1]

def run(base:dict, current:dict, discovered:dict, qa:dict|None=None)->dict:
    old_files={canonical_attachment_url(x.get("url")):x for x in base.get("files",[]) if canonical_attachment_url(x.get("url"))}
    new_files={canonical_attachment_url(x.get("url")):x for x in current.get("files",[]) if canonical_attachment_url(x.get("url"))}
    old_rows={r.get("row_id"):r for r in base.get("rows",[]) if r.get("row_id")}
    new_rows={r.get("row_id"):r for r in current.get("rows",[]) if r.get("row_id")}
    counts=Counter(canonical_attachment_url(r.get("source_attachment_url")) for r in current.get("rows",[]))
    newly_linked=Counter(canonical_attachment_url(r.get("source_attachment_url")) for k,r in new_rows.items() if k not in old_rows)
    posts={}
    failures=[]
    for post in discovered.get("posts",[]):
        if post.get("error"):failures.append({"post_url":post.get("post_url"),"listing_url":post.get("listing_url"),"error":post["error"]})
        for a in post.get("attachments",[]):
            url=canonical_attachment_url(a.get("url"))
            if url:posts[url]={"post_url":post.get("post_url"),"title":post.get("title"),"label":a.get("text")}
    new_summary=[]
    for url,file in sorted(new_files.items()):
        if url in old_files:continue
        new_summary.append({"url":url,
                            "filename":file.get("name") or file.get("filename") or posts.get(url,{}).get("label"),
                            "origin_post":posts.get(url,{}),
                            "bytes":file.get("bytes"),"sha256":file.get("sha256"),
                            "all_linked_rows":counts[url],"new_linked_rows":newly_linked[url],
                            "sheets":[{"sheet":s.get("sheet"),"status":s.get("status"),
                                       "parsed_rows":s.get("parsed_rows"),"rows":s.get("rows"),
                                       "mapping":s.get("mapping")} for s in file.get("sheets",[])]})
    missing_prior=sorted(set(old_files)-set(new_files))
    report={
        "source":"icheon","scope":"diagnostic_only_no_publish",
        "baseline":{"rows":len(old_rows),"files":len(old_files)},
        "after":{"rows":len(new_rows),"files":len(new_files)},
        "new_rows":len(set(new_rows)-set(old_rows)),
        "lost_prior_rows":len(set(old_rows)-set(new_rows)),
        "lost_prior_files":missing_prior,
        "discovery":{"posts":len([p for p in discovered.get("posts",[]) if p.get("post_url")]),
                     "attachments":len(posts),"errors":failures},
        "new_file_details":new_summary,
        "unlinked_new_files":[x for x in new_summary if x["all_linked_rows"]==0],
        "strict_qa":qa or {},
    }
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--baseline",required=True)
    ap.add_argument("--output",default="reports/icheon-live-diagnostic.json")
    ap.add_argument("--qa",default="")
    args=ap.parse_args()
    base=json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    raw=json.loads((ROOT/"data/raw/icheon_expense.json").read_text(encoding="utf-8"))
    discovery=json.loads((ROOT/"reports/capital-backfill-discovery-icheon.json").read_text(encoding="utf-8"))
    try:
        qa=json.loads(Path(args.qa).read_text(encoding="utf-8")) if args.qa else None
    except (OSError,ValueError):
        qa=None
    report=run(base,raw,discovery,qa)
    output=ROOT/args.output
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
