#!/usr/bin/env python3
"""Read-only forensic inspection of exact Incheon Council listing markup.

No guessed msg_seq or file ID, and no publication. Retain the official HTML
and row-bound link evidence to determine whether detailed download requests
can be avoided safely. Each page executes independently.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from capital_backfill import SOURCES, anchors, fetch_text, canonical_attachment_url, title_period, post_like

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--page",type=int,required=True,choices=range(1,6))
    args=ap.parse_args()
    source=next(s for s in SOURCES if s.key=="incheon_council")
    url=source.listing_template.format(page=args.page)
    dest=Path("reports/recovery/incheon-listing-forensics")/f"page-{args.page}"
    dest.mkdir(parents=True,exist_ok=True)
    result={"source":"incheon_council","page":args.page,"list_url":url,
            "publication_authorized":False,"status":"SOURCE_FETCH_NOT_DONE"}
    try:
        html=fetch_text(url)
        (dest/"official-listing.html").write_text(html,encoding="utf-8")
        all_links=anchors(url,html)
        rows=[]
        matched_details=set()
        observed_urls=set()
        for ordinal,match in enumerate(re.finditer(r"<tr\b[^>]*>[\s\S]*?</tr\s*>",html,flags=re.I),1):
            row_html=match.group(0)
            row_links=anchors(url,row_html)
            detail=[a for a in row_links if post_like(a,source)]
            attached=[a for a in row_links if canonical_attachment_url(a.get("url"))]
            expense=re.search(r"업무추진비",row_html) is not None
            if not (detail or attached or expense):
                continue
            for d in detail:
                matched_details.add(d["url"])
            for a in attached:
                observed_urls.add(a["url"])
            # Raw row tags show real javascript form parameters, not inferred
            # download URLs. Keep markup only in the saved original HTML.
            rows.append({"row_number":ordinal,"html_sha256":hashlib.sha256(row_html.encode()).hexdigest(),
                         "expense_mentioned":expense,
                         "detail_links":[{"text":a["text"],"url":a["url"],"onclick":a.get("onclick")} for a in detail],
                         "official_file_links":[{"text":a["text"],"url":a["url"],"onclick":a.get("onclick")} for a in attached],
                         "other_anchor_count":len(row_links)-len(detail)-len(attached),
                         "has_download_word":bool(re.search(r"(?:download|filedown|첨부|파일)",row_html,re.I)),
                         "raw_onclick_attributes":re.findall(r"\bonclick\s*=\s*([\"'])(.*?)\1",row_html,re.I|re.S)[:8],
                         "file_id_attributes":re.findall(r"\b(?:fileno|file_seq|file_id|file_no|atch_file_id)\s*[=:]\s*[\"']?[\w-]+",row_html,re.I)[:12]})
        direct_other=[{"text":a["text"],"url":a["url"]} for a in all_links
                      if canonical_attachment_url(a.get("url")) and a["url"] not in observed_urls]
        result.update({
            "status":"CAPTURED_NOT_PUBLISHABLE",
            "html_sha256":hashlib.sha256(html.encode("utf-8")).hexdigest(),
            "html_length":len(html),"html_anchor_count":len(all_links),
            "rows":rows,"matching_row_count":len(rows),
            "unique_detail_urls":sorted(matched_details),
            "row_bound_download_urls":sorted(observed_urls),
            "unbound_download_links":direct_other[:100],
            "all_file_like_links":[{"url":a["url"],"text":a["text"],"onclick":a.get("onclick")}
                for a in all_links if re.search(r"download|filedown|\.pdf|\.xls|첨부",a["url"]+" "+a["text"]+" "+str(a.get("onclick")),re.I)][:150],
        })
        if not matched_details:
            result["status"]="HOLD_NO_OFFICIAL_DETAIL_LINKS"
    except Exception as exc:
        result.update(status="HOLD_FETCH_FAILED",error=f"{type(exc).__name__}: {exc}")
    (dest/"evidence.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in
                      ("rows","unique_detail_urls","all_file_like_links","unbound_download_links")},
                     ensure_ascii=False),flush=True)
    if result["status"]!="CAPTURED_NOT_PUBLISHABLE":
        raise SystemExit(2)

if __name__=="__main__":
    main()
