#!/usr/bin/env python3
"""Browser-only investigation of Police Agency attachments; never publishes data.

Run on a GitHub Actions Linux runner. Fetch only registered HTTPS police.go.kr
details. Capture browser network/DOM/download evidence, without inventing
attachment URLs or inferring expense merchants from posting titles.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"sources/education_police_registry.json"
OUT=ROOT/"reports/police-browser-attachment-probe.json"
DOWNLOAD_DIR=ROOT/"reports/police-browser-pdfs"
ALLOWED={"police.go.kr","www.police.go.kr"}

def police_url(url: str) -> bool:
    p=urlsplit(url)
    return p.scheme=="https" and p.hostname in ALLOWED and p.port in (None,443)

def police_variants(url: str) -> list[str]:
    if not police_url(url):return []
    p=urlsplit(url)
    if not p.path.startswith(("/user/bbs/","/BZRKZR/user/bbs/")):return [url]
    bare=p.path.removeprefix("/BZRKZR")
    vals=[url]
    for host,path in (("police.go.kr",bare),("www.police.go.kr","/BZRKZR"+bare)):
        val=p._replace(netloc=host,path=path,fragment="").geturl()
        if val not in vals:vals.append(val)
    return vals

def official_download_url(page_url: str, href: str, label: str) -> str:
    """Accept exact PDF attachment controls under Police Agency official file API."""
    if not str(label).strip().lower().endswith(".pdf"):
        return ""
    url=urljoin(page_url,href)
    p=urlsplit(url)
    if not police_url(url):
        return ""
    if p.path!="/component/file/ND_fileDownload.do":
        return ""
    from urllib.parse import parse_qs
    q=parse_qs(p.query)
    if not re.fullmatch(r"\d{3,12}",(q.get("q_fileSn") or [""])[0]):
        return ""
    if not re.fullmatch(r"[0-9a-fA-F-]{32,40}",(q.get("q_fileId") or [""])[0]):
        return ""
    return url

def pdf_metadata(blob: bytes) -> dict:
    """Signature and PDF text sample for format diagnosis, not publication."""
    info={"bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest()}
    if not blob.startswith(b"%PDF-"):
        info["format"]="NOT_PDF"
        return info
    info["format"]="PDF"
    try:
        from io import BytesIO
        from pypdf import PdfReader
        pdf=PdfReader(BytesIO(blob),strict=False)
        info["pages"]=len(pdf.pages)
        info["text_sample"]=(pdf.pages[0].extract_text() or "")[:900] if pdf.pages else ""
    except Exception as e:
        info["parse_error"]=type(e).__name__+": "+str(e)[:150]
    return info

def targets(registry: dict) -> list[dict]:
    source=next(s for s in registry["sources"] if s["key"]=="national_police")
    result=[]
    for seed in source.get("verified_detail_urls",[]):
        if police_url(seed.get("url","")):
            result.append({"title":seed["title"],"url":seed["url"],"role":seed["role"]})
    return result

def stage_pdf_expenses(entry: dict, blob: bytes, role: str, source_url: str, detail_url: str) -> None:
    """Only official PDF user-column rows, never restaurant publication."""
    if not official_download_url(detail_url,source_url,source_url.rsplit("/",1)[-1]+".pdf"):
        # The title-like filename check above is only an API route assertion,
        # not a guessed PDF URI. The exact source_url came from the live DOM.
        entry["parse_error"]="Official PDF endpoint not recognized"
        return
    try:
        from police_expense_pdf import parse_pdf
        rows,summary=parse_pdf(blob,role,source_url)
        for row in rows:
            row["source_detail_url"]=detail_url
        entry["parsed_expenses"]=rows
        entry["expense_summary"]=summary
    except Exception as e:
        entry["parse_error"]=type(e).__name__+": "+str(e)[:240]

def investigate(page, item: dict, output_dir: Path, timeout_ms: int=12000) -> dict:
    result={"title":item["title"],"role":item["role"],"original_url":item["url"],
            "publication_enabled":False,"attempts":[]}
    for url in police_variants(item["url"]):
        entry={"attempted_url":url,"redirect_chain":[],"response_status":None,
               "attachment_candidates":[],"downloads":[]}
        def request_event(request):
            if request.is_navigation_request():
                entry["redirect_chain"].append(request.url[:360])
        page.on("request",request_event)
        try:
            response=page.goto(url,wait_until="domcontentloaded",timeout=timeout_ms)
            entry["final_url"]=page.url
            entry["response_status"]=response.status if response else None
            entry["title"]=page.title()[:200]
            entry["body_sample"]=re.sub(r"\s+"," ",page.locator("body").inner_text(timeout=3000))[:1000]
            if not police_url(page.url):
                entry["blocked"]="UNOFFICIAL_REDIRECT"
            elif not response or response.status!=200:
                entry["blocked"]="NON_200"
            else:
                # DOM evidence may expose opaque JS file-download handlers;
                # never synthesize a download API from unverified ids.
                anchors=page.locator("a,button")
                total=min(anchors.count(),280)
                for i in range(total):
                    loc=anchors.nth(i)
                    try:
                        txt=(loc.inner_text(timeout=450) or "").strip()[:140]
                        href=loc.get_attribute("href",timeout=450) or ""
                        onclick=loc.get_attribute("onclick",timeout=450) or ""
                    except Exception:continue
                    if not re.search(r"pdf|첨부|다운로드|바로보기|download|file",txt+" "+href+" "+onclick,re.I):continue
                    candidate={"text":txt,"href":href[:350],"onclick":onclick[:450],"index":i}
                    entry["attachment_candidates"].append(candidate)
                # Exactly one controlled click on a likely explicit PDF download
                # control; a viewer link must not be mistaken for actual bytes.
                for candidate in entry["attachment_candidates"][:4]:
                    i=candidate["index"]
                    href=candidate["href"]
                    official_download=official_download_url(page.url,href,candidate["text"])
                    if official_download:
                        try:
                            pdf_resp=page.context.request.get(official_download,timeout=timeout_ms)
                            blob=pdf_resp.body()
                            md=pdf_metadata(blob)
                            md["source_url"]=official_download
                            md["status"]=pdf_resp.status
                            entry["downloads"].append(md)
                            if pdf_resp.status==200 and md["format"]=="PDF" and md.get("pages",0)>0:
                                dest=output_dir/(md["sha256"][:16]+".pdf")
                                dest.write_bytes(blob)
                                stage_pdf_expenses(entry,blob,item["role"],official_download,item["url"])
                                break
                        except Exception as e:
                            entry["downloads"].append({"url":official_download,
                                "error":type(e).__name__+": "+str(e)[:150]})
                        # Fall back to a browser download click if cookie-bound API
                        # access still fails, but never click unrelated controls.
                    if candidate["text"] and not candidate["text"].lower().endswith(".pdf"):
                        continue
                    if not re.search(r"pdf|다운로드|download",candidate["text"]+" "+candidate["onclick"],re.I):
                        continue
                    try:
                        with page.expect_download(timeout=4500) as download_info:
                            anchors.nth(i).click(timeout=2800)
                        download=download_info.value
                        temp=output_dir/("temp-"+str(i)+".pdf")
                        download.save_as(temp)
                        blob=temp.read_bytes()
                        md=pdf_metadata(blob)
                        md["suggested_filename"]=download.suggested_filename[:180]
                        if md["format"]=="PDF" and md.get("pages",0)>0:
                            temp.rename(output_dir/(md["sha256"][:16]+".pdf"))
                            source=official_download_url(page.url,candidate["href"],candidate["text"])
                            if source:stage_pdf_expenses(entry,blob,item["role"],source,item["url"])
                        else:temp.unlink(missing_ok=True)
                        entry["downloads"].append(md)
                        break
                    except Exception as e:
                        entry["downloads"].append({"click_index":i,"error":type(e).__name__+": "+str(e)[:130]})
            result["attempts"].append(entry)
            if entry["downloads"] and any(d.get("format")=="PDF" for d in entry["downloads"]):
                break
        except Exception as e:
            entry["exception"]=type(e).__name__+": "+str(e)[:220]
            entry["final_url"]=page.url[:360]
            result["attempts"].append(entry)
        finally:
            page.remove_listener("request",request_event)
    result["verified_pdf_count"]=sum(d.get("format")=="PDF" for a in result["attempts"] for d in a["downloads"])
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--max-posts",type=int,default=2)
    args=p.parse_args()
    registry=json.loads(REGISTRY.read_text(encoding="utf-8"))
    records=targets(registry)[:max(0,min(args.max_posts,5))]
    DOWNLOAD_DIR.mkdir(parents=True,exist_ok=True)
    report={"generated_at":datetime.now(timezone.utc).isoformat(),
            "publication_enabled":False,"mode":"browser_probe_only",
            "records":[]}
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=["--no-sandbox"])
        context=browser.new_context(locale="ko-KR",viewport={"width":1365,"height":900},
                                    accept_downloads=True,ignore_https_errors=False)
        page=context.new_page()
        for item in records:
            print("PROBE",item["title"],flush=True)
            record=investigate(page,item,DOWNLOAD_DIR)
            report["records"].append(record)
            print("RESULT",json.dumps({"title":item["title"],
                  "statuses":[a["response_status"] for a in record["attempts"]],
                  "candidates":sum(len(a["attachment_candidates"]) for a in record["attempts"]),
                  "pdfs":record["verified_pdf_count"],
                  "errors":[a.get("exception","") for a in record["attempts"]]},ensure_ascii=False),flush=True)
        context.close()
        browser.close()
    report["verified_pdf_count"]=sum(x["verified_pdf_count"] for x in report["records"])
    staged=[]
    for record in report["records"]:
        for attempt in record["attempts"]:
            staged.extend(attempt.get("parsed_expenses") or [])
    seen={r["row_id"]:r for r in staged}
    staged=list(seen.values())
    report["staged_transactions"]=len(staged)
    staged_path=ROOT/"data/raw/police_expense_staging.json"
    staged_path.parent.mkdir(parents=True,exist_ok=True)
    staged_path.write_text(json.dumps({"publication_enabled":False,
       "source":"police_browser_pdf","transactions":staged},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("VERIFIED_POLICE_PDFS",report["verified_pdf_count"],"STAGED_TRANSACTIONS",len(staged),flush=True)

if __name__=="__main__":
    main()
