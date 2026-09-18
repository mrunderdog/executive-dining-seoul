#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0 Safari/537.36"

LISTING = "https://www.gg.go.kr/bbs/board.do?bcIdx=535&bsIdx=535&menuId=1778&page={page}"
FILE_EXTS = (".xlsx", ".xls", ".csv")

# Official monthly executive boards. These are intentionally tracked even when
# the current client-rendered list cannot be crawled from GitHub Actions.
ROLE_TARGETS = [
    {"role":"도지사","url":"https://www.gg.go.kr/bbs/board.do?bsIdx=803&menuId=1768"},
    {"role":"행정1부지사","url":"https://www.gg.go.kr/bbs/board.do?bsIdx=804&menuId=1769"},
    {"role":"행정2부지사","url":"https://www.gg.go.kr/bbs/board.do?bsIdx=805&menuId=1770"},
    {"role":"경제부지사","url":"https://www.gg.go.kr/bbs/board.do?bsIdx=806&menuId=1771"},
]

# Verified official 2026 Q1 detail pages and attachment endpoints. The listing
# and detail pages intermittently time out in GitHub Actions, while the direct
# attachment route is stable enough to be used as a resilience seed. Seeds are
# source lineage, not manually invented expense rows.
SEED_POSTS = {
    2026: [
        {
            "title":"2026년 1분기 시책추진업무추진비 사용내역(건설정책과)",
            "department":"건설정책과","period":[2026,None,1],
            "url":"https://www.gg.go.kr/bbs/boardView.do?bIdx=232294031&bcIdx=536&bsIdx=535&menuId=1778&page=1",
            "attachments":[{"text":"(건설정책과) 2026년 1분기 시책업무추진비 공개자료.xlsx","url":"https://www.gg.go.kr/cmmn/download.do?idx=891854","seeded":True}],
        },
        {
            "title":"2026년 1분기 시책추진업무추진비 사용내역(기획예산담당관)",
            "department":"기획예산담당관","period":[2026,None,1],
            "url":"https://www.gg.go.kr/bbs/boardView.do?bIdx=231836438&bcIdx=536&bsIdx=535&menuId=1778&page=1",
            "attachments":[{"text":"2026년 1분기 시책추진업무추진비 공개자료(기획예산담당관).xlsx","url":"https://www.gg.go.kr/cmmn/download.do?idx=891679","seeded":True}],
        },
        {
            "title":"2026년 1분기 시책추진업무추진비 사용내역(보도기획담당관)",
            "department":"보도기획담당관","period":[2026,None,1],
            "url":"https://www.gg.go.kr/bbs/boardView.do?bIdx=232981004&bcIdx=536&bsIdx=535&menuId=1778&page=1",
            "attachments":[{"text":"2026년 1분기 시책추진업무추진비 공개자료(보도기획담당관).xlsx","url":"https://www.gg.go.kr/cmmn/download.do?idx=892063","seeded":True}],
        },
        {
            "title":"2026년 1분기 시책추진업무추진비 사용내역(식품안전과)",
            "department":"식품안전과","period":[2026,None,1],
            "url":"https://www.gg.go.kr/bbs/boardView.do?bIdx=231607772&bcIdx=536&bsIdx=535&menuId=1778&page=1",
            "attachments":[{"text":"2026년 1분기 시책추진업무추진비 공개자료(식품안전과).xlsx","url":"https://www.gg.go.kr/cmmn/download.do?idx=891513","seeded":True}],
        },
        {
            "title":"2026년 1분기 시책추진업무추진비 사용내역(기획담당관)",
            "department":"기획담당관","period":[2026,None,1],
            "url":"https://www.gg.go.kr/bbs/boardView.do?bIdx=232751906&bcIdx=536&bsIdx=535&menuId=1778&page=1",
            "attachments":[{"text":"2026년 1분기 시책추진업무추진비 공개자료(기획담당관).xlsx","url":"https://www.gg.go.kr/cmmn/download.do?idx=891941","seeded":True}],
        },
        {
            "title":"2026년 1분기 시책추진업무추진비 사용내역(AI프런티어정책과)",
            "department":"AI프런티어정책과","period":[2026,None,1],
            "url":"https://www.gg.go.kr/bbs/boardView.do?bIdx=232065193&bcIdx=536&bsIdx=535&menuId=1778&page=1",
            "attachments":[{"text":"2026년 1분기 시책추진 업무추진비 공개자료_AI프런티어정책과.xlsx","url":"https://www.gg.go.kr/cmmn/download.do?idx=891793","seeded":True}],
        },
        {
            "title":"2026년 1분기 시책추진업무추진비 사용내역(정책홍보담당관)",
            "department":"정책홍보담당관","period":[2026,None,1],
            "url":"https://www.gg.go.kr/bbs/boardView.do?bIdx=231607782&bcIdx=536&bsIdx=535&menuId=1778&page=1",
            "attachments":[{"text":"2026년 1분기 시책추진업무추진비 공개자료(정책홍보담당관).xlsx","url":"https://www.gg.go.kr/cmmn/download.do?idx=891527","seeded":True}],
        },
        {
            "title":"2026년 1분기 시책추진업무추진비 사용내역(평생교육과)",
            "department":"평생교육과","period":[2026,None,1],
            "url":"https://www.gg.go.kr/bbs/boardView.do?bIdx=231836421&bcIdx=536&bsIdx=535&menuId=1778&page=1",
            "attachments":[{"text":"2026년 1분기 시책추진업무추진비 공개자료(평생교육과).xlsx","url":"https://www.gg.go.kr/cmmn/download.do?idx=891648","seeded":True}],
        },
        {
            "title":"2026년 1분기 시책추진업무추진비 사용내역(공공기관담당관)",
            "department":"공공기관담당관","period":[2026,None,1],
            "url":"https://www.gg.go.kr/bbs/boardView.do?bIdx=231836409&bcIdx=536&bsIdx=535&menuId=1778&page=1",
            "attachments":[{"text":"2026년 1분기 시책추진업무추진비 공개자료(공공기관담당관).xlsx","url":"https://www.gg.go.kr/cmmn/download.do?idx=891634","seeded":True}],
        },
        {
            "title":"2026년 1분기 시책추진업무추진비 사용내역(노인복지과)",
            "department":"노인복지과","period":[2026,None,1],
            "url":"https://www.gg.go.kr/bbs/boardView.do?bIdx=232294023&bcIdx=536&bsIdx=535&menuId=1778&page=1",
            "attachments":[{"text":"2026년 1분기 업무추진비 공개자료(노인복지과).xlsx","url":"https://www.gg.go.kr/cmmn/download.do?idx=891846","seeded":True}],
        },
        {
            "title":"2026년 1분기 시책추진업무추진비 사용내역(택시교통과)",
            "department":"택시교통과","period":[2026,None,1],
            "url":"https://www.gg.go.kr/bbs/boardView.do?bIdx=232751899&bcIdx=536&bsIdx=535&menuId=1778&page=1",
            "attachments":[{"text":"2026년 1분기 시책추진업무추진비 공개자료(택시교통과).xlsx","url":"https://www.gg.go.kr/cmmn/download.do?idx=891928","seeded":True}],
        },
    ]
}


class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.anchors=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag.lower()=="a":
            self.stack.append({"href":attrs.get("href",""),"onclick":attrs.get("onclick",""),"title":attrs.get("title",""),"text":[]})
        elif self.stack and tag.lower()=="img":
            for k in ("alt","title"):
                if attrs.get(k): self.stack[-1]["text"].append(attrs[k])
    def handle_data(self, data):
        if self.stack: self.stack[-1]["text"].append(data)
    def handle_endtag(self, tag):
        if tag.lower()=="a" and self.stack:
            x=self.stack.pop()
            x["text"]=" ".join(" ".join([x.get("title",""),*x["text"]]).split())
            self.anchors.append(x)


def decode(raw: bytes, charset: str | None) -> str:
    for c in (charset,"utf-8","cp949","euc-kr"):
        if not c: continue
        try: return raw.decode(c)
        except Exception: pass
    return raw.decode("utf-8",errors="replace")


def fetch(url: str) -> str:
    headers={
        "User-Agent":UA,
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language":"ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.5",
        "Cache-Control":"no-cache",
        "Referer":"https://www.gg.go.kr/",
    }
    last=None
    for timeout in (12,20):
        try:
            req=urllib.request.Request(url,headers=headers)
            with urllib.request.urlopen(req,timeout=timeout) as r:
                return decode(r.read(),r.headers.get_content_charset())
        except Exception as e:
            last=e
    raise last


def onclick_url(base: str, value: str) -> str | None:
    if not value: return None
    for raw in re.findall(r"['\"]([^'\"]+)['\"]",html.unescape(value)):
        if any(x in raw.lower() for x in ("boardview","download","file","attach",".do")):
            return urllib.parse.urljoin(base,raw)
    return None


def links(base: str, doc: str) -> list[dict]:
    p=AnchorParser(); p.feed(doc); out=[]; seen=set()
    for a in p.anchors:
        href=html.unescape(a.get("href","")).strip(); url=None
        if href and href!="#" and not href.lower().startswith("javascript:"):
            url=urllib.parse.urljoin(base,href)
        else:
            url=onclick_url(base,a.get("onclick",""))
        if not url or url in seen: continue
        seen.add(url); out.append({"text":a.get("text",""),"url":url})
    return out


def quarter_from(text: str):
    m=re.search(r"(20\d{2})\D{0,5}([1-4])\s*분기",text)
    if m: return [int(m.group(1)),None,int(m.group(2))]
    return None


def department_from(title: str) -> str:
    m=re.search(r"\(([^()]+)\)\s*$",title)
    return m.group(1).strip() if m else ""


def looks_post(x: dict, year: int) -> bool:
    s=(x.get("text","")+" "+x.get("url",""))
    return "boardView.do" in x.get("url","") and "업무추진비" in s and str(year) in s


def looks_file(x: dict) -> bool:
    s=(x.get("text","")+" "+x.get("url","")).lower()
    return any(ext in s for ext in FILE_EXTS) or any(k in s for k in ("download","filedown","attach","atchfile"))


def regex_file_fallback(base: str, doc: str) -> list[dict]:
    out=[]; seen=set()
    for m in re.finditer(r"['\"]([^'\"]*(?:download|filedown|attach|atchfile)[^'\"]*)['\"]",doc,flags=re.I):
        url=urllib.parse.urljoin(base,html.unescape(m.group(1)))
        if url not in seen:
            seen.add(url); out.append({"text":"attachment","url":url})
    return out



def crawl_seed_posts(year: int, max_posts: int = 300) -> tuple[list[dict], list[dict]]:
    """Fallback for the JS-rendered board listing.

    Official detail pages expose previous/next boardView links and attachment download
    links in server-rendered HTML, so walk the same board from a verified yearly seed.
    """
    queue=list(SEED_POSTS.get(year) or [])
    seen=set()
    posts=[]
    errors=[]
    while queue and len(seen) < max_posts:
        item=queue.pop(0)
        url=item.get("url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        title=item.get("title") or ""
        seed_atts=[a for a in (item.get("attachments") or []) if a.get("url")]
        if seed_atts:
            posts.append({
                "source":"gyeonggi_province",
                "region":"경기",
                "jurisdiction":"경기도",
                "institution":"경기도청",
                "title":title,
                "department":item.get("department") or department_from(title),
                "role":item.get("role") or "",
                "period":item.get("period") or quarter_from(title),
                "post_url":url,
                "attachments":seed_atts,
                "discovery_mode":"verified_attachment_seed",
            })
        try:
            doc=fetch(url)
        except Exception as e:
            errors.append({"url":url,"error":f"seed detail {type(e).__name__}: {e}"})
            continue

        # Discover adjacent posts from this exact board.
        for x in links(url,doc):
            u=x.get("url") or ""
            txt=x.get("text") or ""
            if "boardView.do" not in u or "bsIdx=535" not in u:
                continue
            if "업무추진비" not in txt or str(year) not in txt:
                continue
            if u not in seen and all(q.get("url") != u for q in queue):
                queue.append({"title":txt,"url":u})

        if "업무추진비" not in title or str(year) not in title:
            continue
        atts=[x for x in links(url,doc) if looks_file(x)]
        if not atts:
            atts=regex_file_fallback(url,doc)
        if atts:
            posts.append({
                "source":"gyeonggi_province",
                "region":"경기",
                "jurisdiction":"경기도",
                "institution":"경기도청",
                "title":title,
                "department":item.get("department") or department_from(title),
                "role":item.get("role") or "",
                "period":item.get("period") or quarter_from(title),
                "post_url":url,
                "attachments":atts,
                "discovery_mode":"detail_chain",
            })
    return posts, errors

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,default=datetime.now().year)
    ap.add_argument("--pages",type=int,default=20)
    args=ap.parse_args()

    posts=[]; seen=set(); errors=[]
    for page in range(1,args.pages+1):
        url=LISTING.format(page=page)
        try:
            doc=fetch(url)
        except Exception as e:
            errors.append({"url":url,"error":f"{type(e).__name__}: {e}"})
            break
        found=[x for x in links(url,doc) if looks_post(x,args.year)]
        if not found and page==1:
            # Preserve diagnostics if the official board changes to client-side rendering.
            errors.append({"url":url,"error":"NO_SERVER_RENDERED_POST_LINKS"})
        for x in found:
            if x["url"] in seen: continue
            seen.add(x["url"])
            title=x["text"]
            row={
                "source":"gyeonggi_province",
                "region":"경기",
                "jurisdiction":"경기도",
                "institution":"경기도청",
                "title":title,
                "department":department_from(title),
                "period":quarter_from(title),
                "post_url":x["url"],
                "attachments":[],
            }
            try:
                detail=fetch(x["url"])
                atts=[f for f in links(x["url"],detail) if looks_file(f)]
                if not atts: atts=regex_file_fallback(x["url"],detail)
                row["attachments"]=atts
            except Exception as e:
                row["error"]=f"{type(e).__name__}: {e}"
            posts.append(row)

    # Always merge verified seeds. They are the resilience path when the official
    # client-rendered listing or detail pages time out from GitHub Actions.
    fallback_posts,fallback_errors=crawl_seed_posts(args.year)
    posts.extend(fallback_posts)
    errors.extend(fallback_errors)

    # Stable de-duplication. Prefer the version with more downloadable
    # attachments so a successful live crawl can supersede a seed, but a
    # transient empty live result cannot erase the seed.
    by_url={}
    for p in posts:
        u=p.get("post_url")
        if not u:
            continue
        current=by_url.get(u)
        if current is None or sum(bool(a.get("url")) for a in p.get("attachments",[])) > sum(bool(a.get("url")) for a in current.get("attachments",[])):
            by_url[u]=p
    posts=list(by_url.values())

    REPORTS.mkdir(exist_ok=True)
    payload={
        "generated_at":datetime.now().isoformat(timespec="seconds"),
        "year":args.year,
        "listing_template":LISTING,
        "role_targets":ROLE_TARGETS,
        "posts":posts,
        "errors":errors,
    }
    (REPORTS/"gyeonggi-executive-discovery.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

    downloadable=sum(1 for p in posts for a in p.get("attachments",[]) if a.get("url"))
    md=[
        f"# Gyeonggi executive source discovery — {args.year}","",
        f"- Posts: **{len(posts)}**",
        f"- Downloadable attachments: **{downloadable}**",
        f"- Errors: **{len(errors)}**","",
        "## Monthly executive role targets","",
    ]
    md.extend(f"- {x['role']}: {x['url']}" for x in ROLE_TARGETS)
    md += [
        "",
        "| Department | Period | Attachments | Post |",
        "|---|---|---:|---|",
    ]
    for p in posts[:300]:
        md.append(f"| {p.get('department') or '-'} | {p.get('period') or '-'} | {len(p.get('attachments',[]))} | {p.get('post_url')} |")
    if errors:
        md+=["","## Errors",""]
        md.extend(f"- {e}" for e in errors)
    (REPORTS/"gyeonggi-executive-discovery.md").write_text("\n".join(md)+"\n",encoding="utf-8")

    print(json.dumps({"posts":len(posts),"attachments":downloadable,"errors":errors[:10]},ensure_ascii=False))
    if not posts:
        raise SystemExit("No Gyeonggi executive posts discovered; inspect discovery report")


if __name__=="__main__":
    main()
