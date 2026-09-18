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
UA = "ExecutiveDiningSeoul/2.2 (+https://github.com/mrunderdog/executive-dining-seoul)"

LISTINGS = [
    {"key":"mayor","role":"시장","url":"https://www.incheon.go.kr/open/OPEN010301"},
    {"key":"vice_mayor","role":"부시장","url":"https://www.incheon.go.kr/open/OPEN010303"},
    {"key":"headquarters","role":"본청 실국과장","url":"https://www.incheon.go.kr/open/OPEN010305"},
]

# Verified official detail IDs are a resilience seed, not a substitute for live
# discovery. Incheon list/detail HTML intermittently times out from GitHub
# Actions, while its official attachment endpoint remains stable. These seeds
# keep the latest verified 2026 mayor/vice-mayor disclosures ingestible.
SEED_POSTS_2026 = [
    {"scope":"mayor","role":"시장","month":1,"upper_no":3064270,"files":3},
    {"scope":"mayor","role":"시장","month":2,"upper_no":3065798,"files":3},
    {"scope":"mayor","role":"시장","month":3,"upper_no":3068575,"files":3},
    {"scope":"mayor","role":"시장","month":4,"upper_no":3071498,"files":3},
    {"scope":"mayor","role":"시장","month":6,"upper_no":3081521,"files":3},
    {"scope":"vice_mayor","role":"행정부시장","month":1,"upper_no":3064272,"files":2},
    {"scope":"vice_mayor","role":"정무부시장","month":1,"upper_no":3064273,"files":2},
    {"scope":"vice_mayor","role":"행정부시장","month":2,"upper_no":3065801,"files":2},
    {"scope":"vice_mayor","role":"정무부시장","month":2,"upper_no":3065802,"files":2},
    {"scope":"vice_mayor","role":"행정부시장","month":3,"upper_no":3068576,"files":2},
    {"scope":"vice_mayor","role":"정무부시장","month":3,"upper_no":3068581,"files":2},
    {"scope":"vice_mayor","role":"행정부시장","month":4,"upper_no":3071499,"files":2},
    {"scope":"vice_mayor","role":"정무부시장","month":4,"upper_no":3071500,"files":2},
    {"scope":"vice_mayor","role":"행정부시장","month":5,"upper_no":3076689,"files":2},
    {"scope":"vice_mayor","role":"정무부시장","month":5,"upper_no":3076690,"files":2},
    {"scope":"vice_mayor","role":"행정부시장","month":6,"upper_no":3081522,"files":2},
    {"scope":"vice_mayor","role":"정무부시장","month":6,"upper_no":3081524,"files":2},
]


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
        except (LookupError,UnicodeDecodeError): pass
    return raw.decode("utf-8",errors="replace")


def fetch(url: str) -> str:
    req=urllib.request.Request(url,headers={
        "User-Agent":UA,
        "Accept":"text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language":"ko-KR,ko;q=0.9,en;q=0.6",
    })
    last=None
    for timeout in (12,20):
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                return decode(r.read(),r.headers.get_content_charset())
        except Exception as e:
            last=e
    raise last


def onclick_url(base: str, value: str) -> str | None:
    if not value: return None
    for raw in re.findall(r"['\"]([^'\"]+)['\"]",html.unescape(value)):
        if any(x in raw.lower() for x in ("getfile","download","attach","open0103")):
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
        seen.add(url)
        out.append({"text":a.get("text",""),"url":url})
    return out


def detail_like(x: dict, listing: dict, year: int) -> bool:
    u=x.get("url",""); text=x.get("text","")
    path=urllib.parse.urlparse(listing["url"]).path.rstrip("/")
    if not re.search(re.escape(path)+r"/\d+(?:\?|$)",u):
        return False
    if str(year) not in text and str(year-1) not in text:
        return False
    return "업무추진비" in text


def file_like(x: dict) -> bool:
    s=(x.get("text","")+" "+x.get("url","")).lower()
    return ".pdf" in s or "getfile" in s or "download" in s or "attach" in s


def period_from(text: str):
    m=re.search(r"(20\d{2})\D{0,5}(1[0-2]|0?[1-9])\s*월",text)
    if m: return [int(m.group(1)),int(m.group(2)),None]
    return None


def actor_from(title: str, default: str) -> str:
    s=" ".join(str(title or "").split())
    if "정무부시장" in s: return "정무부시장"
    if "행정부시장" in s: return "행정부시장"
    if re.search(r"(^|\s)시장($|\s|업무)",s): return "시장"
    return default


def seeded_posts(year: int) -> list[dict]:
    if year != 2026:
        return []
    out=[]
    for seed in SEED_POSTS_2026:
        base="OPEN010301" if seed["scope"]=="mayor" else "OPEN010303"
        title=f"{year}년 {seed['month']}월 {seed['role']} 업무추진비 사용내역"
        attachments=[]
        for file_no in range(1,int(seed["files"])+1):
            attachments.append({
                "text":f"{seed['role']} 업무추진비 {year}-{seed['month']:02d} file-{file_no}.pdf",
                "url":(
                    "https://www.incheon.go.kr/comm/getFile"
                    f"?fileNo={file_no}&fileTy=ATTACH&srvcId=BBSTY1&upperNo={seed['upper_no']}"
                ),
                "seeded":True,
            })
        out.append({
            "source":"incheon_metropolitan_government",
            "region":"인천",
            "jurisdiction":"인천광역시",
            "institution":"인천광역시청",
            "scope":seed["scope"],
            "role":seed["role"],
            "title":title,
            "period":[year,seed["month"],None],
            "post_url":f"https://www.incheon.go.kr/open/{base}/{seed['upper_no']}",
            "attachments":attachments,
            "discovery_mode":"verified_detail_seed",
        })
    return out


def merge_seed_posts(posts: list[dict], year: int) -> list[dict]:
    by_post={p.get("post_url"):p for p in posts if p.get("post_url")}
    for seed in seeded_posts(year):
        current=by_post.get(seed["post_url"])
        if current and any(a.get("url") for a in current.get("attachments",[])):
            continue
        by_post[seed["post_url"]]=seed
    return list(by_post.values())


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,default=datetime.now().year)
    ap.add_argument("--pages",type=int,default=5)
    args=ap.parse_args()

    posts=[]; errors=[]; seen=set()
    for listing in LISTINGS:
        for page in range(1,args.pages+1):
            url=listing["url"] if page==1 else f"{listing['url']}?curPage={page}"
            try:
                doc=fetch(url)
            except Exception as e:
                errors.append({"scope":listing["key"],"url":url,"error":f"{type(e).__name__}: {e}"})
                break
            found=[x for x in links(url,doc) if detail_like(x,listing,args.year)]
            if not found and page>1:
                break
            for x in found:
                if x["url"] in seen: continue
                seen.add(x["url"])
                try:
                    detail=fetch(x["url"])
                    atts=[a for a in links(x["url"],detail) if file_like(a)]
                except Exception as e:
                    errors.append({"scope":listing["key"],"url":x["url"],"error":f"detail {type(e).__name__}: {e}"})
                    atts=[]
                posts.append({
                    "source":"incheon_metropolitan_government",
                    "region":"인천",
                    "jurisdiction":"인천광역시",
                    "institution":"인천광역시청",
                    "scope":listing["key"],
                    "role":actor_from(x.get("text",""),listing["role"]),
                    "title":x.get("text",""),
                    "period":period_from(x.get("text","")),
                    "post_url":x["url"],
                    "attachments":atts,
                })

    posts=merge_seed_posts(posts,args.year)
    posts.sort(key=lambda p:(p.get("period") or [0,0,0],p.get("role") or "",p.get("post_url") or ""),reverse=True)

    REPORTS.mkdir(exist_ok=True)
    out=REPORTS/"incheon-executive-discovery.json"
    payload={"generated_at":datetime.now().isoformat(timespec="seconds"),"year":args.year,"posts":posts,"errors":errors}
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    downloadable=sum(1 for p in posts for a in p.get("attachments",[]) if a.get("url"))
    md=[
        f"# Incheon executive source discovery — {args.year}","",
        f"- Posts: **{len(posts)}**",
        f"- Downloadable attachments: **{downloadable}**",
        f"- Errors: **{len(errors)}**","",
        "| Scope | Role | Period | Attachments | Post |",
        "|---|---|---|---:|---|",
    ]
    for p in posts[:200]:
        md.append(f"| {p.get('scope')} | {p.get('role')} | {p.get('period') or '-'} | {len(p.get('attachments',[]))} | {p.get('post_url')} |")
    if errors:
        md += ["","## Errors",""]
        md.extend(f"- {e}" for e in errors)
    (REPORTS/"incheon-executive-discovery.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"posts":len(posts),"downloadable":downloadable,"errors":len(errors)},ensure_ascii=False))
    if not posts or not downloadable:
        raise SystemExit("Incheon executive discovery produced no downloadable posts")


if __name__=="__main__":
    main()
