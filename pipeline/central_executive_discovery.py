#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "sources" / "central_executive_registry.json"
REPORTS = ROOT / "reports"
UA = "ExecutiveDiningSeoul/2.1 (+https://github.com/mrunderdog/executive-dining-seoul)"
FILE_EXTS = (".xlsx", ".xls", ".csv", ".pdf", ".hwp", ".hwpx")
EXPENSE_WORDS = ("업무추진비", "업무 추진비", "장관", "차관", "처장", "차장", "실국장", "실·국장", "기관장")


class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.anchors=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag.lower()=="a":
            self.stack.append({"href":attrs.get("href", ""), "onclick":attrs.get("onclick", ""), "title":attrs.get("title", ""), "text":[]})
        elif self.stack and tag.lower()=="img":
            for k in ("alt", "title"):
                if attrs.get(k): self.stack[-1]["text"].append(attrs[k])
    def handle_data(self, data):
        if self.stack: self.stack[-1]["text"].append(data)
    def handle_endtag(self, tag):
        if tag.lower()=="a" and self.stack:
            x=self.stack.pop(); x["text"]=" ".join(" ".join([x.get("title", ""), *x["text"]]).split()); self.anchors.append(x)


def decode(raw: bytes, charset: str | None) -> str:
    for c in [charset, "utf-8", "cp949", "euc-kr"]:
        if not c: continue
        try: return raw.decode(c)
        except (LookupError, UnicodeDecodeError): pass
    return raw.decode("utf-8", errors="replace")


def fetch(url: str) -> str:
    req=urllib.request.Request(url, headers={"User-Agent":UA, "Accept":"text/html,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return decode(r.read(), r.headers.get_content_charset())


def onclick_url(base: str, value: str) -> str | None:
    if not value: return None
    for raw in re.findall(r"['\"]([^'\"]+)['\"]", html.unescape(value)):
        if any(x in raw.lower() for x in ("download", "file", "attach", ".do", ".jsp")):
            return urllib.parse.urljoin(base, raw)
    return None


def parse_links(base: str, doc: str) -> list[dict]:
    p=AnchorParser(); p.feed(doc); out=[]; seen=set()
    for a in p.anchors:
        href=html.unescape(a.get("href", "")).strip(); url=None
        if href and href!="#" and not href.lower().startswith("javascript:"):
            url=urllib.parse.urljoin(base, href)
        else:
            url=onclick_url(base, a.get("onclick", ""))
        if not url or url in seen: continue
        seen.add(url); out.append({"text":a.get("text", ""), "url":url})
    return out


def looks_file(x: dict) -> bool:
    s=(x.get("text", "")+" "+x.get("url", "")).lower()
    return any(ext in s for ext in FILE_EXTS) or any(t in s for t in ("download", "filedown", "attach", "atchfile"))


def relevant(x: dict, year: int) -> bool:
    text=(x.get("text", "")+" "+x.get("url", ""))
    return any(w in text for w in EXPENSE_WORDS) and (str(year) in text or str(year-1) in text or "업무추진비" in text)


def extract_year_month(text: str):
    m=re.search(r"(20\d{2})\D{0,4}(1[0-2]|0?[1-9])\s*월", text)
    if m: return int(m.group(1)), int(m.group(2))
    m=re.search(r"(20\d{2})\D{0,4}([1-4])\s*분기", text)
    if m: return int(m.group(1)), None
    return None, None


def discover_source(src: dict, year: int) -> dict:
    result={"key":src["key"], "institution":src["institution"], "verified":bool(src.get("verified")), "role_scope":src.get("role_scope", ""), "format_hint":src.get("format_hint", ""), "pages":[], "attachments":[], "errors":[]}
    if not src.get("verified"):
        result["status"]="DISCOVERY_REQUIRED"; return result
    seen_att=set(); seen_page=set()
    for listing in src.get("listing_urls") or []:
        try: doc=fetch(listing)
        except Exception as e:
            result["errors"].append(f"listing {listing}: {type(e).__name__}: {e}"); continue
        links=parse_links(listing, doc)
        result["pages"].append(listing)
        direct=[x for x in links if looks_file(x) and relevant(x, year)]
        detail=[x for x in links if not looks_file(x) and relevant(x, year)][:40]
        for x in direct:
            if x["url"] not in seen_att:
                seen_att.add(x["url"]); y,m=extract_year_month(x["text"]); result["attachments"].append({**x,"year":y,"month":m,"parent":listing})
        for x in detail:
            if x["url"] in seen_page: continue
            seen_page.add(x["url"])
            try: ddoc=fetch(x["url"])
            except Exception: continue
            for f in parse_links(x["url"], ddoc):
                if not looks_file(f): continue
                label=(x.get("text", "")+" "+f.get("text", "")).strip()
                if not relevant({"text":label,"url":f["url"]}, year): continue
                if f["url"] in seen_att: continue
                seen_att.add(f["url"]); y,m=extract_year_month(label); result["attachments"].append({"text":label,"url":f["url"],"year":y,"month":m,"parent":x["url"]})
    parseable=sum(any(ext in (a.get("text","")+" "+a.get("url","")).lower() for ext in (".xlsx",".xls",".csv",".hwpx",".pdf")) for a in result["attachments"])
    result["parseable_attachments"]=parseable
    result["status"]="PARSEABLE_FOUND" if parseable else ("FILES_FOUND_UNSUPPORTED" if result["attachments"] else ("FETCH_FAILED" if result["errors"] else "NO_FILES_FOUND"))
    return result


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--year",type=int,default=datetime.now().year); ap.add_argument("--source"); args=ap.parse_args()
    reg=json.loads(REGISTRY.read_text(encoding="utf-8")); sources=[x for x in reg.get("sources",[]) if not args.source or x.get("key")==args.source]
    rows=[]
    workers=min(8,max(1,len(sources)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map={pool.submit(discover_source,x,args.year):x for x in sources}
        for fut in as_completed(future_map):
            src=future_map[fut]
            try:
                rows.append(fut.result())
            except Exception as e:
                rows.append({
                    "key":src["key"],"institution":src["institution"],
                    "verified":bool(src.get("verified")),"role_scope":src.get("role_scope",""),
                    "format_hint":src.get("format_hint",""),"pages":[],"attachments":[],
                    "errors":[f"worker {type(e).__name__}: {e}"],"parseable_attachments":0,
                    "status":"FETCH_FAILED",
                })
    order={x.get("key"):i for i,x in enumerate(sources)}
    rows.sort(key=lambda r:order.get(r.get("key"),9999))
    REPORTS.mkdir(exist_ok=True)
    out=REPORTS / "central-executive-discovery.json"; out.write_text(json.dumps({"generated_at":datetime.now().isoformat(timespec="seconds"),"year":args.year,"sources":rows},ensure_ascii=False,indent=2),encoding="utf-8")
    md=[f"# Central executive source discovery — {args.year}","","| Institution | Status | Files | Parseable |","|---|---|---:|---:|"]
    for r in rows: md.append(f"| {r['institution']} | {r['status']} | {len(r['attachments'])} | {r.get('parseable_attachments',0)} |")
    (REPORTS / "central-executive-discovery.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"sources":len(rows),"parseable_sources":sum(r.get('parseable_attachments',0)>0 for r in rows),"files":sum(len(r['attachments']) for r in rows)},ensure_ascii=False))

if __name__=="__main__": main()
