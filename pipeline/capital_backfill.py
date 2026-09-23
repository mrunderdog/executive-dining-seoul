#!/usr/bin/env python3
"""Discover official expense posts/attachments for first Capital Area adapters.

This intentionally stages source lineage first. Attachment discovery is automatic; row parsing is
handled separately and may only publish after schema/quality checks.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
UA = "ExecutiveDiningSeoul/1.1 (+https://github.com/mrunderdog/executive-dining-seoul)"


@dataclass
class Source:
    key: str
    region: str
    jurisdiction: str
    institution: str
    listing_template: str
    max_pages: int
    kind: str
    active_from: tuple[int, int] | None = None


SOURCES = [
    Source("suwon", "경기", "수원시", "수원특례시의회", "https://council.suwon.go.kr/kr/costBBS.do?flag=all&page={page}", 20, "monthly"),
    Source("hwaseong", "경기", "화성시", "화성특례시의회", "https://council.hscity.go.kr/cnts/bbs/boardList.php?bbsCd=cns&bbsSubCd=cns08&pageNo={page}", 12, "monthly"),
    Source("goyang", "경기", "고양시", "고양특례시의회", "https://www.goyangcouncil.go.kr/kr/costBBS.do?flag=all&page={page}", 10, "quarterly"),
    Source("seongnam", "경기", "성남시", "성남시의회", "https://www.sncouncil.go.kr/kr/news/bbsCost.do?pageNum={page}", 10, "quarterly"),
    Source("bucheon", "경기", "부천시", "부천시의회", "https://council.bucheon.go.kr/kr/intro/bbsInfo.do?pageNum={page}", 15, "monthly"),
    Source("namyangju", "경기", "남양주시", "남양주시의회", "https://nyjc.go.kr/content/dataroom/propelclosed.html", 1, "quarterly"),
    Source("uijeongbu", "경기", "의정부시", "의정부시의회", "https://www.ujbcl.go.kr/svc/bbs/BusinessList.do?bbsMnuCd=MNU002300000650400000666&pageNo={page}", 8, "quarterly"),
    Source("gwangmyeong", "경기", "광명시", "광명시의회", "https://council.gm.go.kr/kr/costBBS.do?flag=all&page={page}", 8, "quarterly"),
    Source("gimpo", "경기", "김포시", "김포시의회", "https://gimpocouncil.go.kr/cnts/bbs/infoList.php?bbsCd=act&bbsSubCd=act0702", 1, "quarterly"),
    Source("ansan", "경기", "안산시", "안산시의회", "https://www.ansan.go.kr/council/common/bbs/selectPageListBbs.do?bbs_code=B0406", 1, "quarterly"),
    Source("paju", "경기", "파주시", "파주시의회", "https://www.pajucouncil.go.kr/content/data/operatingExpense.html?page={page}", 4, "quarterly"),
    Source("anseong", "경기", "안성시", "안성시의회", "https://anseongcl.go.kr/kr/costBBS.do?flag=all&page={page}", 12, "monthly"),
    Source("icheon", "경기", "이천시", "이천시의회", "https://council.icheon.go.kr/content/information/businessOperatingExpense.html?page={page}", 4, "monthly"),
    Source("osan", "경기", "오산시", "오산시의회", "https://www.osancouncil.go.kr/kr/info/bbs?bbs_id=work&page={page}", 15, "monthly"),
    Source("pocheon", "경기", "포천시", "포천시의회", "https://council.pocheon.go.kr/kr/news/bbsBusiness.do?flag=all&pageNum={page}", 15, "monthly"),
    Source("yangpyeong", "경기", "양평군", "양평군의회", "https://www.ypcouncil.go.kr/main/selectBbsNttList.do?bbsNo=9&integrDeptCode=&key=43&pageIndex={page}&pageUnit=10&searchCnd=all&searchCtgry=&searchKrwd=", 12, "monthly"),
    Source("yongin", "경기", "용인시", "용인특례시의회", "https://council.yongin.go.kr/kr/costBBS.do?flag=all&page={page}", 12, "monthly"),
    Source("gwangju", "경기", "광주시", "광주시의회", "https://www.gjcouncil.go.kr/kr/costBBS.do?flag=all&page={page}", 12, "monthly"),
    Source("guri", "경기", "구리시", "구리시의회", "https://www.gcc.or.kr/board/news/list.do?tbname=cost&page={page}", 16, "monthly"),
    Source("uiwang", "경기", "의왕시", "의왕시의회", "https://council.uiwang.go.kr/kr/Information/bbsCost.do?flag=all&pageNum={page}", 12, "monthly"),
    Source("gunpo", "경기", "군포시", "군포시의회", "https://www.gunpocouncil.go.kr/kr/costBBS.do?flag=all&page={page}", 10, "monthly"),
    Source("dongducheon", "경기", "동두천시", "동두천시의회", "https://council.ddc.go.kr/kr/news/bbsCost.do?flag=all&page={page}", 12, "monthly"),
    Source("gwacheon", "경기", "과천시", "과천시의회", "https://www.gccouncil.go.kr/kr/costBBS.do?flag=all&page={page}", 12, "monthly"),
    Source("gapyeong", "경기", "가평군", "가평군의회", "https://www.gpassem.go.kr/kr/operations2BBS.do?flag=all&page={page}", 10, "quarterly"),
    Source("siheung", "경기", "시흥시", "시흥시의회", "https://www.siheungcouncil.go.kr/content/activity/business.html?page={page}", 5, "quarterly"),
    Source("yeoju", "경기", "여주시", "여주시의회", "https://yeojucouncil.go.kr/kr/costBBS.do?flag=all&page={page}", 12, "monthly"),
    Source("yangju", "경기", "양주시", "양주시의회", "https://yjcc.yangju.go.kr/yjcc/selectBbsNttList.do?bbsNo=302&key=2559&pageIndex={page}", 5, "quarterly"),
    Source("hanam", "경기", "하남시", "하남시의회", "https://council.hanam.go.kr/content/community/business.html?page={page}", 24, "monthly"),
    Source("yeoncheon", "경기", "연천군", "연천군의회", "https://www.yca21.go.kr/board/news/list.do?tbname=cost&page={page}", 12, "monthly"),
    Source("bupyeong", "인천", "부평구", "부평구의회", "https://council.icbp.go.kr/kr/news/bbs?bbs_id=expense&page={page}", 15, "monthly"),
    Source("jemulpo", "인천", "제물포구", "제물포구의회", "https://council.jemulpo.go.kr/council/kr/costBBS.do?flag=all&page={page}", 4, "monthly", (2026, 7)),
    Source("yeongjong", "인천", "영종구", "영종구의회", "https://www.yeongjong.go.kr/council/pst/list.do?pst_id=cncl_ofcl_exp", 1, "monthly", (2026, 7)),
    Source("seohae", "인천", "서해구", "서해구의회", "https://www.seohae.go.kr/open_content/council/activity/open.jsp", 1, "monthly", (2026, 7)),
    Source("michuhol", "인천", "미추홀구", "미추홀구의회", "https://www.michuhol.go.kr/ndsys/ndBBs/bbs_list.asp?bbs_category=&bbs_code=board_189&class_code=&dept_idx=&gotopage={page}&keyfield=&keyword=", 8, "monthly"),
    Source("yeonsu", "인천", "연수구", "연수구의회", "https://council.yeonsu.go.kr/kr/businessBBS.do?flag=all&page={page}", 12, "monthly"),
    Source("gyeyang", "인천", "계양구", "계양구의회", "https://council.gyeyang.go.kr/kr/costBBS.do?flag=all&page={page}", 12, "monthly"),
    Source("ganghwa", "인천", "강화군", "강화군의회", "https://council.ganghwa.go.kr/kr/workBBS.do?flag=all&page={page}", 12, "monthly"),
    Source("ongjin", "인천", "옹진군", "옹진군의회", "https://council.ongjin.go.kr/kr/costBBS.do?flag=all&page={page}", 8, "quarterly"),
    Source("gyeonggi_council", "경기", "경기도", "경기도의회", "https://www.ggc.go.kr/site/main/duty/list?cp={page}&listType=list&sortOrder=DT_USE_DT", 12, "quarterly"),
    Source("incheon_council", "인천", "인천광역시", "인천광역시의회", "https://www.icouncil.go.kr/main/bbs/bbsMsgList.do?bcd=infordisc&pgno={page}", 25, "monthly"),
]


class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == "a":
            self.stack.append({
                "href": attrs.get("href", ""),
                "onclick": attrs.get("onclick", ""),
                "title": attrs.get("title", ""),
                "attrs": attrs,
                "text": [],
            })
            return
        if self.stack and tag.lower() == "img":
            for field in ("alt", "title"):
                if attrs.get(field):
                    self.stack[-1]["text"].append(attrs[field])

    def handle_data(self, data):
        if self.stack:
            self.stack[-1]["text"].append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.stack:
            x = self.stack.pop()
            pieces = [x.get("title", ""), *x["text"]]
            x["text"] = " ".join(" ".join(pieces).split())
            self.anchors.append(x)


def decode_html(raw: bytes, header_charset: str | None) -> str:
    candidates = []
    if header_charset:
        candidates.append(header_charset)
    head = raw[:10000].decode("ascii", errors="ignore")
    m = re.search(r"charset\s*=\s*['\"]?([A-Za-z0-9._-]+)", head, flags=re.I)
    if m:
        candidates.append(m.group(1))
    candidates += ["utf-8", "cp949", "euc-kr"]
    seen = set()
    best = None
    for charset in candidates:
        c = charset.lower()
        if c in seen:
            continue
        seen.add(c)
        try:
            text = raw.decode(charset)
        except (LookupError, UnicodeDecodeError):
            continue
        # Prefer a clean Korean decode when the page contains expected public-board words.
        score = sum(text.count(k) for k in ("업무추진비", "의회", "첨부", "파일"))
        if best is None or score > best[0]:
            best = (score, text)
    if best:
        return best[1]
    return raw.decode("utf-8", errors="replace")


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=15) as r:
        raw = r.read()
        charset = r.headers.get_content_charset()
    return decode_html(raw, charset)


def onclick_url(base: str, onclick: str) -> str | None:
    if not onclick:
        return None
    # Capture a URL/string used by location.href, window.open, fn_view('...') etc.
    candidates = re.findall(r"['\"]([^'\"]+(?:\.do|/bbs|download|file)[^'\"]*)['\"]", html.unescape(onclick), flags=re.I)
    if not candidates:
        return None
    return urllib.parse.urljoin(base, candidates[0])


def anchors(url: str, text: str):
    p = AnchorParser(); p.feed(text)
    out = []
    for a in p.anchors:
        href = html.unescape(a.get("href", "")).strip()
        resolved = None
        if href and href != "#" and not href.lower().startswith("javascript:"):
            resolved = urllib.parse.urljoin(url, href)
        else:
            resolved = onclick_url(url, a.get("onclick", ""))
        if not resolved:
            continue
        attrs = a.get("attrs") or {}
        low = resolved.lower()
        if "bbsattachdownload.do" in low and "key=" not in low:
            haystacks = [a.get("onclick", "")] + [str(v) for v in attrs.values()]
            key = ""
            for raw in haystacks:
                m = re.search(r"(?:key\s*[=:]\s*|['\"])([0-9a-f]{32,128})(?:['\"]|$)", html.unescape(str(raw)), flags=re.I)
                if m:
                    key = m.group(1)
                    break
            if key:
                sep = "&" if "?" in resolved else "?"
                resolved = f"{resolved}{sep}key={urllib.parse.quote(key)}"
        out.append({"text": a.get("text", ""), "url": resolved, "onclick": a.get("onclick", "")})
    return out


def title_period(title: str):
    normalized = title.replace("년", " ").replace(".", " ").replace("-", " ").replace("/", " ")
    m = re.search(r"(20\d{2})\s+(\d{1,2})\s*월", normalized)
    if m:
        return int(m.group(1)), int(m.group(2)), None
    m = re.search(r"(20\d{2})\s*년?\s*([1-4])\s*/\s*4\s*분기", title)
    if m:
        return int(m.group(1)), None, int(m.group(2))
    m = re.search(r"(?:(20)?(\d{2}))\s*년(?:도)?\s*([1-4])\s*분기", title)
    if m:
        year = int((m.group(1) or "20") + m.group(2))
        return year, None, int(m.group(3))
    # Some boards put institution/purpose words between year and quarter,
    # e.g. "2026년 파주시의회 업무추진비 내역(1분기)".
    m = re.search(r"(20\d{2})[^\n]{0,100}?([1-4])\s*분기", title)
    if m:
        return int(m.group(1)), None, int(m.group(2))
    return None


def period_overlaps(period, since: tuple[int, int], until: tuple[int, int]):
    if not period:
        return False
    y, m, q = period
    if q:
        lo = (y, 1 + (q - 1) * 3); hi = (y, q * 3)
    else:
        lo = hi = (y, m)
    return not (hi < since or lo > until)


def post_like(a, src: Source):
    t, u = a["text"], a["url"]
    if "업무추진비" not in t:
        return False
    if src.key in {"suwon", "goyang", "jemulpo", "yongin", "gwangju", "gunpo", "gwacheon", "yeoju", "dongducheon"}:
        return "costBBSview" in u or "costbbsview" in u.lower()
    if src.key in {"icheon", "paju"}:
        low = u.lower()
        return "operatingexpense.html" in low and "fidx=" in low and "pg=vv" in low
    if src.key == "ansan":
        low = u.lower()
        return "selectbbsdetail.do" in low and "bbs_code=b0406" in low
    if src.key == "michuhol":
        return "bbs_view.asp" in u.lower() and "board_189" in u.lower()
    if src.key == "bupyeong":
        return "expense" in u and ("reform=view" in u.lower() or "bbs" in u.lower())
    if src.key == "yeonsu":
        return "businessbbsview" in u.lower()
    if src.key in {"gyeyang", "ongjin"}:
        return "costbbsview" in u.lower()
    if src.key == "ganghwa":
        return "workbbsview" in u.lower()
    if src.key == "incheon_council":
        return "bbsmsgdetail.do" in u.lower() and "bcd=infordisc" in u.lower()
    return True


def attachment_like(a):
    # Expense attachment filenames themselves normally contain '업무추진비', so never exclude on that word.
    t, u = a["text"].lower(), a["url"].lower()
    file_ext = any(ext in t or ext in u for ext in (".xlsx", ".xls", ".csv", ".pdf", ".zip"))
    file_route = any(token in u for token in ("download", "filedown", "attach", "atchfile", "bbsfile"))
    return file_ext or file_route


def regex_attachment_fallback(base: str, text: str):
    results = []
    seen = set()
    # Recover download URLs embedded in onclick/script attributes.
    for m in re.finditer(r"['\"]([^'\"]*(?:download|filedown|attach|atchfile|bbsfile)[^'\"]*)['\"]", text, flags=re.I):
        raw = html.unescape(m.group(1))
        url = urllib.parse.urljoin(base, raw)
        if "bbsattachdownload.do" in url.lower() and "key=" not in url.lower():
            nearby = text[max(0, m.start()-500):min(len(text), m.end()+500)]
            km = re.search(r"(?:key\s*[=:]\s*|['\"])([0-9a-f]{32,128})(?:['\"]|$)", nearby, flags=re.I)
            if km:
                sep = "&" if "?" in url else "?"
                url = f"{url}{sep}key={urllib.parse.quote(km.group(1))}"
        if url not in seen:
            seen.add(url); results.append({"text": "attachment", "url": url})
    # At minimum preserve visible XLS/XLSX filenames for lineage even if the board hides the URL in JS.
    for m in re.finditer(r"([^<>\"']+\.(?:xlsx?|csv|pdf))", text, flags=re.I):
        filename = " ".join(html.unescape(m.group(1)).split())[-220:]
        marker = "name:" + filename
        if marker not in seen:
            seen.add(marker); results.append({"text": filename, "url": ""})
    return results


def canonical_attachment_url(url: str) -> str | None:
    """Normalize real attachment URLs and reject obvious HTML/CSS pseudo-links."""
    raw = html.unescape(str(url or "")).strip()
    if not raw or " " in raw:
        return None
    p = urllib.parse.urlsplit(raw)
    path = p.path.lower().rstrip("/")
    query = urllib.parse.parse_qsl(p.query, keep_blank_values=False)
    # Bare route names and UI fragments are not downloadable files.
    if path.endswith("/attach"):
        return None
    if path.endswith("/bbsattachdownload.do") and not query:
        return None
    if not (
        re.search(r"\.(?:xlsx?|csv|pdf|zip)$", path, flags=re.I)
        or any(token in path for token in ("download", "filedown", "attach", "atchfile", "bbsfile"))
    ):
        return None
    query.sort()
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(query), ""))


def sanitize_discovered_posts(posts):
    """De-duplicate attachments globally within one source discovery.

    Some council list pages repeat the same download controls on every paged
    result. Keeping them once avoids dozens of identical downloads and prevents
    a list-page wrapper from being treated as many distinct expense files.
    """
    seen = set()
    cleaned = []
    for post in posts:
        row = dict(post)
        atts = []
        for att in post.get("attachments", []):
            canon = canonical_attachment_url(att.get("url"))
            if not canon or canon in seen:
                continue
            seen.add(canon)
            item = dict(att)
            item["url"] = canon
            atts.append(item)
        row["attachments"] = atts
        cleaned.append(row)
    return cleaned


def discover_source(src: Source, since, until):
    effective_since = max(since, src.active_from) if src.active_from else since
    seen_posts = set(); posts = []
    empty_pages = 0
    for page in range(1, src.max_pages + 1):
        url = src.listing_template.format(page=page)
        try:
            doc = fetch_text(url)
        except Exception as e:
            posts.append({"source": src.key, "listing_url": url, "error": f"listing {type(e).__name__}: {e}"})
            break
        before_page = len(posts)
        page_anchors = anchors(url, doc)

        if src.key == "gimpo":
            for tr in re.findall(r"<tr\b[^>]*>.*?</tr>", doc, flags=re.I|re.S):
                plain = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(tr)).split())
                if "업무추진비" not in plain:
                    continue
                period = title_period(plain)
                if not period_overlaps(period, effective_since, until):
                    continue
                row_links = anchors(url, tr)
                found = [x for x in row_links if attachment_like(x)]
                if not found:
                    found = regex_attachment_fallback(url, tr)
                found = [x for x in found if x.get("url")]
                if not found:
                    continue
                post_key = f"{period}|{plain[:120]}"
                if post_key in seen_posts:
                    continue
                seen_posts.add(post_key)
                posts.append({
                    "source":src.key,"region":src.region,"jurisdiction":src.jurisdiction,
                    "institution":src.institution,"title":plain,"period":period,
                    "post_url":url,"attachments":found,
                })

        for a in page_anchors:
            title=a.get("text","")
            direct_period=title_period(title)
            if "업무추진비" in title and attachment_like(a) and period_overlaps(direct_period, effective_since, until):
                direct_key="direct:"+a.get("url","")
                if direct_key not in seen_posts:
                    seen_posts.add(direct_key)
                    posts.append({
                        "source":src.key,"region":src.region,"jurisdiction":src.jurisdiction,
                        "institution":src.institution,"title":title,"period":direct_period,
                        "post_url":url,"attachments":[{"text":title or "attachment","url":a["url"]}],
                    })
                continue
            if src.key == "gyeonggi_council":
                title=a.get("text","")
                period=title_period(title)
                if not period_overlaps(period, effective_since, until):
                    continue
                # The official Gyeonggi Council list links the title directly to
                # an XLS/XLSX download. Keep only chair/vice-chair leadership files.
                if "업무추진비" not in title or not re.search(r"\((?:의장|1부의장|2부의장)\)", title):
                    continue
                if "/file/download/" not in a.get("url",""):
                    continue
                if a["url"] in seen_posts:
                    continue
                seen_posts.add(a["url"])
                posts.append({
                    "source":src.key,"region":src.region,"jurisdiction":src.jurisdiction,
                    "institution":src.institution,"title":title,"period":period,
                    "post_url":url,"attachments":[{"text":title+".xlsx","url":a["url"]}],
                })
                continue
            if not post_like(a, src):
                continue
            period = title_period(a["text"])
            if not period_overlaps(period, effective_since, until) or a["url"] in seen_posts:
                continue
            seen_posts.add(a["url"])
            row = {
                "source": src.key, "region": src.region, "jurisdiction": src.jurisdiction,
                "institution": src.institution, "title": a["text"], "period": period,
                "post_url": a["url"], "attachments": [],
            }
            try:
                detail = fetch_text(a["url"])
                found = [x for x in anchors(a["url"], detail) if attachment_like(x)]
                if not found:
                    found = regex_attachment_fallback(a["url"], detail)
                row["attachments"] = found
            except Exception as e:
                row["error"] = f"detail {type(e).__name__}: {e}"
            posts.append(row)

        # Once target-period posts have been found, two consecutive pages
        # that add nothing mean we have moved beyond the useful backfill window.
        if len(posts) > before_page:
            empty_pages = 0
        else:
            empty_pages += 1
            if posts and empty_pages >= 2:
                break
    return sanitize_discovered_posts(posts)


def ym(s: str):
    y, m = s.split("-")
    return int(y), int(m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2024-12")
    ap.add_argument("--until", default=datetime.now().strftime("%Y-%m"))
    ap.add_argument("--source", choices=[s.key for s in SOURCES])
    args = ap.parse_args()
    since, until = ym(args.since), ym(args.until)
    selected = [s for s in SOURCES if not args.source or s.key == args.source]
    rows = []
    for src in selected:
        rows.extend(discover_source(src, since, until))

    REPORTS.mkdir(parents=True, exist_ok=True)
    suffix = f"-{args.source}" if args.source else ""
    out_json = REPORTS / f"capital-backfill-discovery{suffix}.json"
    out_md = REPORTS / f"capital-backfill-discovery{suffix}.md"

    # Public boards can transiently time out or change markup. Never replace a
    # previously usable source map with a zero-result discovery.
    fresh_posts = [x for x in rows if x.get("post_url")]
    fresh_downloadable = sum(
        1
        for x in fresh_posts
        for a in x.get("attachments", [])
        if canonical_attachment_url(a.get("url"))
    )
    if args.source and out_json.exists() and (not fresh_posts or fresh_downloadable == 0):
        try:
            previous = json.loads(out_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
        previous_posts = [x for x in previous.get("posts", []) if x.get("post_url")]
        previous_downloadable = sum(
            1
            for x in previous_posts
            for a in x.get("attachments", [])
            if canonical_attachment_url(a.get("url"))
        )
        if previous_posts and previous_downloadable:
            print(json.dumps({
                "source": args.source,
                "status": "STALE_OK",
                "reason": "fresh discovery returned no usable downloadable posts",
                "fresh_posts": len(fresh_posts),
                "fresh_downloadable": fresh_downloadable,
                "preserved_posts": len(previous_posts),
                "preserved_downloadable": previous_downloadable,
            }, ensure_ascii=False))
            print(out_json)
            return

    result = {"generated_at": datetime.now().isoformat(timespec="seconds"), "since": args.since, "until": args.until, "sources": [s.key for s in selected], "posts": rows}
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"# Capital area backfill discovery — {args.since} ~ {args.until}", ""]
    for src in selected:
        rr = [x for x in rows if x.get("source") == src.key]
        good = [x for x in rr if x.get("post_url")]
        attachments = sum(len(x.get("attachments", [])) for x in good)
        downloadable = sum(1 for x in good for a in x.get("attachments", []) if a.get("url"))
        lines += [f"## {src.institution}", "", f"- Posts: {len(good)}", f"- Attachment records: {attachments}", f"- Downloadable attachment URLs: {downloadable}", ""]
        for x in good[:30]:
            lines.append(f"- [{x['title']}]({x['post_url']}) — attachments {len(x.get('attachments', []))}")
        lines.append("")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"posts": sum(1 for x in rows if x.get("post_url")), "attachments": sum(len(x.get("attachments", [])) for x in rows)}, ensure_ascii=False))
    print(out_json)


if __name__ == "__main__":
    main()
