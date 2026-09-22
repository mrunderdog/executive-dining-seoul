#!/usr/bin/env python3
"""Download and normalize council expense spreadsheets discovered from official sources.

Stage 1 supports Goyang's quarterly XLS/XLSX attachments. Output is a raw canonical layer,
NOT the published restaurant ranking. Publication remains gated by entity matching/scoring.
"""
from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import io
import json
import re
import urllib.request
import zipfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
RAW_DIR = ROOT / "data" / "raw"
DISCOVERY = REPORTS / "capital-backfill-discovery.json"
UA = "ExecutiveDiningSeoul/1.0 (+https://github.com/mrunderdog/executive-dining-seoul)"

ALIASES = {
    "date": ["사용일", "사용일자", "집행일", "집행일자", "일자", "일시", "날짜", "사용일시", "집행일시", "결제일", "이용일", "승인일"],
    "time": ["사용시간", "집행시간", "시간"],
    "merchant": ["집행장소", "사용처", "사용장소", "장소", "업소명", "상호", "가맹점명"],
    "address": ["주소", "소재지", "집행장소주소", "사용처주소"],
    "purpose": ["집행목적", "사용목적", "목적", "내용", "적요"],
    "people": ["인원", "참석인원", "대상인원", "사용인원"],
    "amount": ["금액", "집행금액", "사용금액", "결제금액", "지출금액"],
    "role": ["사용자", "사용자명", "직책", "직위", "집행자", "부서명", "부서", "구분"],
    "method": ["결제방법", "지급방법", "결제수단"],
}


def clean_text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.isoformat()
    return " ".join(str(v).replace("\n", " ").split()).strip()


def norm_header(v) -> str:
    return re.sub(r"[\s()\[\]·ㆍ._/-]+", "", clean_text(v)).lower()


def parse_amount(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return int(round(v))
    s = re.sub(r"[^0-9.-]", "", clean_text(v))
    if not s:
        return None
    try:
        return int(round(float(s)))
    except ValueError:
        return None


def parse_people(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return int(v)
    m = re.search(r"(\d+)", clean_text(v))
    return int(m.group(1)) if m else None


def valid_transaction_merchant(v) -> bool:
    s = clean_text(v)
    if not s or s in {"-", "–", "—"}:
        return False
    if re.fullmatch(r"[0-9,.:\-\s]+", s):
        return False
    compact_s = re.sub(r"\s+", "", s)
    structural = (
        "업무추진비집행내역",
        "업무추진비사용내역",
        "의회운영업무추진비집행내역",
        "기관운영업무추진비집행내역",
        "시책추진업무추진비집행내역",
        "인원사용방법",
        "단위:원",
        "단위：원",
    )
    if any(token in compact_s for token in structural):
        return False
    if compact_s in {"합계", "총계", "누계", "계", "사용처", "집행장소", "장소"}:
        return False
    return True


def recover_date_from_row(row, source_period):
    """Recover a transaction date from common abbreviated council formats.

    Only uses the source publication year/month/quarter as context; it never
    invents a day. This is mainly for PDF/XLS rows where the date header is
    split or the row uses forms such as '8. 5.' or '5일'.
    """
    if not source_period or not source_period[0]:
        return ""
    year, month_hint, _quarter = source_period
    vals = [clean_text(x) for x in row[:4]]
    probes = [v for v in vals if v]
    probes += [f"{vals[i]} {vals[i+1]}".strip() for i in range(min(3, len(vals)-1)) if vals[i] or vals[i+1]]
    for s in probes:
        m = re.search(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", s)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
            except ValueError:
                pass
        m = re.fullmatch(r"\s*(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[.]?\s*(?:\([^)]*\))?\s*", s)
        if m:
            try:
                return date(int(year), int(m.group(1)), int(m.group(2))).isoformat()
            except ValueError:
                pass
        m = re.fullmatch(r"\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일(?:\s*\([^)]*\))?\s*", s)
        if m:
            try:
                return date(int(year), int(m.group(1)), int(m.group(2))).isoformat()
            except ValueError:
                pass
        if month_hint:
            m = re.fullmatch(r"\s*(\d{1,2})\s*일(?:\s*\([^)]*\))?\s*", s)
            if m:
                try:
                    return date(int(year), int(month_hint), int(m.group(1))).isoformat()
                except ValueError:
                    pass
    return ""


def parse_date(v):
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = clean_text(v)
    if not s:
        return ""
    m = re.search(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass
    return s


def _html_attachment_candidates(base_url: str, blob: bytes) -> list[str]:
    text = blob.decode("utf-8", errors="ignore")
    candidates = []
    patterns = [
        r'''(?:src|href|data)\s*=\s*["']([^"']+)["']''',
        r'''["']([^"']+\.(?:pdf|xlsx?|xls|csv|zip)(?:\?[^"']*)?)["']''',
        r'''["']([^"']*(?:download|filedown|attach|atchfile|bbsfile)[^"']*)["']''',
    ]
    seen = set()
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.I):
            raw = html.unescape(m.group(1)).strip()
            if not raw or raw.lower().startswith(("javascript:", "data:")):
                continue
            url = urllib.parse.urljoin(base_url, raw)
            low = url.lower()
            if not any(token in low for token in (".pdf", ".xlsx", ".xls", ".csv", ".zip", "download", "filedown", "attach", "atchfile", "bbsfile")):
                continue
            if url == base_url or url in seen:
                continue
            seen.add(url)
            candidates.append(url)
    return candidates


def fetch_binary(url: str, referer: str = "", _depth: int = 0) -> bytes:
    """Download public-board attachments with browser-like session semantics.

    Several council endpoints return a small HTML viewer/wrapper rather than
    the attachment bytes. Follow one nested PDF/download target when present.
    """
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    base_headers = {
        "User-Agent": UA,
        "Accept": "application/pdf,application/zip,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,text/csv,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.6",
    }
    if referer:
        base_headers["Referer"] = referer
        try:
            warm = urllib.request.Request(
                referer,
                headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8", "Accept-Language": base_headers["Accept-Language"]},
            )
            with opener.open(warm, timeout=25) as r:
                r.read(2048)
        except Exception:
            pass

    last_exc = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=base_headers)
            with opener.open(req, timeout=75) as r:
                blob = r.read()
                ctype = (r.headers.get("Content-Type") or "").lower()
                final_url = r.geturl()
            head = blob[:512].lstrip().lower()
            is_html = (
                "text/html" in ctype
                or head.startswith(b"<!doctype html")
                or head.startswith(b"<html")
            )
            if is_html:
                if _depth < 2:
                    for nested in _html_attachment_candidates(final_url or url, blob):
                        try:
                            return fetch_binary(nested, final_url or url, _depth + 1)
                        except Exception:
                            continue
                raise ValueError(f"attachment endpoint returned HTML wrapper with no usable file ({ctype or 'unknown content-type'})")
            if len(blob) < 32:
                raise ValueError(f"attachment response too small ({len(blob)} bytes)")
            return blob
        except Exception as exc:
            last_exc = exc
            if attempt == 2:
                break
    raise last_exc


def workbook_rows(blob: bytes, filename: str):
    lower = filename.lower()
    # Some councils publish monthly disclosures as a ZIP containing one or
    # more XLS/XLSX/PDF files. Expand those archives before treating PK bytes
    # as an Office Open XML workbook.
    if lower.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            yielded = False
            for member in zf.namelist():
                if member.endswith("/") or member.startswith("__MACOSX/"):
                    continue
                ml = member.lower()
                if not ml.endswith((".xlsx", ".xls", ".pdf", ".csv")):
                    continue
                inner = zf.read(member)
                for sheet_name, rows in workbook_rows(inner, member):
                    yielded = True
                    yield f"{member}::{sheet_name}", rows
            if not yielded:
                raise ValueError("ZIP contained no supported spreadsheet/PDF files")
        return
    if blob.startswith(b"PK") or lower.endswith(".xlsx"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            yield ws.title, rows
        return
    if blob.startswith(bytes.fromhex("D0CF11E0A1B11AE1")) or lower.endswith(".xls"):
        import xlrd
        book = xlrd.open_workbook(file_contents=blob)
        for sh in book.sheets():
            rows = [sh.row_values(i) for i in range(sh.nrows)]
            yield sh.name, rows
        return
    if blob.startswith(b"%PDF") or lower.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(blob))
        yielded = False
        for pageno, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text(extraction_mode="layout") or page.extract_text() or ""
            except TypeError:
                text = page.extract_text() or ""
            rows = []
            for line in text.splitlines():
                cells = [x.strip() for x in re.split(r"\s{2,}|\t+", line.strip()) if x.strip()]
                if cells:
                    rows.append(cells)
            if rows:
                yielded = True
                yield f"pdf-page-{pageno}", rows
        if not yielded:
            raise ValueError("PDF contained no extractable text rows")
        return
    raise ValueError("unsupported spreadsheet/PDF format")


def header_score(row):
    cells = [norm_header(x) for x in row]
    matched = set()
    for field, aliases in ALIASES.items():
        for c in cells:
            if any(norm_header(a) == c or norm_header(a) in c for a in aliases if c):
                matched.add(field); break
    score = len(matched)
    if "merchant" in matched: score += 2
    if "amount" in matched: score += 2
    if "date" in matched: score += 1
    return score, matched


def find_header(rows):
    best = (-1, -1, set())
    for i, row in enumerate(rows[:40]):
        score, matched = header_score(row)
        if score > best[0]:
            best = (score, i, matched)
    return best if best[0] >= 4 else None


def map_columns(row):
    result = {}
    # Role-like headers are unusually ambiguous: a single table may contain
    # both "부서명" and the actual payer/user ("사용자"). Resolve all other
    # fields left-to-right, then choose role by semantic priority instead of
    # whichever role-like header appears first.
    for idx, cell in enumerate(row):
        c = norm_header(cell)
        if not c:
            continue
        for field, aliases in ALIASES.items():
            if field == "role" or field in result:
                continue
            if any(norm_header(a) == c or norm_header(a) in c for a in aliases):
                result[field] = idx

    role_priority = ("사용자", "사용자명", "직책", "직위", "집행자", "부서명", "부서", "구분")
    cells = [norm_header(x) for x in row]
    for alias in role_priority:
        a = norm_header(alias)
        hit = next((idx for idx, value in enumerate(cells) if value and (a == value or a in value)), None)
        if hit is not None:
            result["role"] = hit
            break
    return result


def cell(row, mapping, field):
    idx = mapping.get(field)
    return row[idx] if idx is not None and idx < len(row) else None


def infer_leadership_role(title):
    s=clean_text(title)
    if re.search(r"(?:^|[^가-힣])1\s*부의장",s) or re.search(r"\(1부의장\)",s): return "1부의장"
    if re.search(r"(?:^|[^가-힣])2\s*부의장",s) or re.search(r"\(2부의장\)",s): return "2부의장"
    if "부의장" in s: return "부의장"
    m=re.search(r"([가-힣A-Za-z0-9·]+위원장)",s)
    if m: return m.group(1)
    if "의장" in s: return "의장"
    return ""


def infer_pdf_context_role(rows):
    """Infer a leadership section title from the top of a PDF page.

    Council PDF disclosures often put a heading such as "의장 업무추진비
    집행내역" on a page that has no table header, followed by several pages of
    tables with no repeated role label. Only inspect the top/title area and
    require explicit leadership wording near 업무추진비/집행내역 so merchant or
    purpose text containing '의장협의회' cannot change the payer role.
    """
    head = " ".join(
        clean_text(cell)
        for row in rows[:14]
        for cell in row
        if clean_text(cell)
    )
    if not head:
        return ""
    patterns = [
        (r"(?:업무추진비|집행내역)[^\n]{0,40}\b1\s*부의장\b", "1부의장"),
        (r"\b1\s*부의장\b[^\n]{0,40}(?:업무추진비|집행내역)", "1부의장"),
        (r"(?:업무추진비|집행내역)[^\n]{0,40}\b2\s*부의장\b", "2부의장"),
        (r"\b2\s*부의장\b[^\n]{0,40}(?:업무추진비|집행내역)", "2부의장"),
        (r"(?:업무추진비|집행내역)[^\n]{0,40}\b부의장\b", "부의장"),
        (r"\b부의장\b[^\n]{0,40}(?:업무추진비|집행내역)", "부의장"),
        (r"(?:업무추진비|집행내역)[^\n]{0,40}(?:^|[^가-힣])의장(?:$|[^가-힣])", "의장"),
        (r"(?:^|[^가-힣])의장(?:$|[^가-힣])[^\n]{0,40}(?:업무추진비|집행내역)", "의장"),
    ]
    for pattern, role in patterns:
        if re.search(pattern, head):
            return role
    # Parenthetical labels in a title are also sufficiently explicit.
    return infer_leadership_role_from_purpose(head)


def infer_leadership_role_from_purpose(value):
    """Recover payer leadership only from explicit parenthetical/bracket labels.

    Some councils publish a generic user value (e.g. 안성시의회) and put the
    accountable chair in the purpose text as "(의장)" or "(부의장)". Keep this
    deliberately strict so phrases such as "시군의회의장협의회" are not
    misclassified as payer roles.
    """
    s = clean_text(value)
    if re.search(r"[\(\[]\s*1\s*부의장\s*[\)\]]", s):
        return "1부의장"
    if re.search(r"[\(\[]\s*2\s*부의장\s*[\)\]]", s):
        return "2부의장"
    if re.search(r"[\(\[]\s*부의장\s*[\)\]]", s):
        return "부의장"
    if re.search(r"[\(\[]\s*의장\s*[\)\]]", s):
        return "의장"
    return ""


def resolve_role(cell_value, sheet_name, default_role, purpose=""):
    """Prefer explicit leadership context over generic department labels."""
    cell_role = clean_text(cell_value)
    explicit = infer_leadership_role(cell_role)
    if explicit:
        return explicit
    purpose_role = infer_leadership_role_from_purpose(purpose)
    if purpose_role:
        return purpose_role
    contextual = infer_leadership_role(sheet_name) or infer_leadership_role(default_role)
    if contextual:
        return contextual
    return cell_role or clean_text(default_role) or clean_text(sheet_name)

def normalize_sheet(rows, sheet_name, source_meta):
    found = find_header(rows)
    if not found:
        return [], {"sheet": sheet_name, "status": "NO_HEADER", "rows": len(rows)}
    score, hi, matched = found
    mapping = map_columns(rows[hi])
    # PDF disclosures often put the accountable role in a section title above
    # the repeated table header, e.g. "업무추진비 집행내역(부의장)", while the
    # table itself contains only 대상인원. Preserve that page/section context.
    preamble = " ".join(
        clean_text(cell)
        for row in rows[max(0, hi - 8):hi]
        for cell in row
        if clean_text(cell)
    )
    section_role = infer_leadership_role(preamble)
    # "구분" is ambiguous across councils. Some use it for leadership roles,
    # while others use it for expense categories such as 급식비/기타.
    # Keep it as a role column only when sampled values actually contain a
    # recognizable leadership title; otherwise allow sheet/file context to
    # supply the role instead of polluting the dataset with category labels.
    role_idx = mapping.get("role")
    if role_idx is not None and norm_header(rows[hi][role_idx] if role_idx < len(rows[hi]) else "") == "구분":
        samples = [
            clean_text(r[role_idx])
            for r in rows[hi + 1:hi + 31]
            if role_idx < len(r) and clean_text(r[role_idx])
        ]
        if samples and not any(infer_leadership_role(v) for v in samples):
            mapping.pop("role", None)
    out = []
    blank_run = 0
    last_used_date = ""
    for ri, row in enumerate(rows[hi + 1:], start=hi + 2):
        if not any(clean_text(x) for x in row):
            blank_run += 1
            if blank_run >= 8 and out: break
            continue
        blank_run = 0
        merchant = clean_text(cell(row, mapping, "merchant"))
        amount = parse_amount(cell(row, mapping, "amount"))
        raw_date_value = cell(row, mapping, "date")
        raw_date_text = clean_text(raw_date_value)
        if any(token in raw_date_text.replace(" ", "") for token in ("사용내역없음", "해당없음", "내역없음")):
            continue
        if merchant and (
            not valid_transaction_merchant(merchant)
            or merchant.replace(" ", "") in {"신용카드", "카드", "현금", "계좌이체"}
        ):
            continue
        used_date = parse_date(raw_date_value)
        date_inferred = False
        # parse_date deliberately preserves unknown text for structural-row
        # detection. For transaction rows, however, abbreviated values such as
        # "8. 5." must still reach the context-aware recovery logic.
        full_date = bool(re.fullmatch(r"20\d{2}-\d{2}-\d{2}", used_date or ""))
        if not full_date:
            recovered_date = recover_date_from_row(row, source_meta.get("period"))
            if recovered_date:
                used_date = recovered_date
                date_inferred = True
        # Excel disclosure sheets frequently merge the date cell across several
        # transaction rows. openpyxl/xlrd expose only the first merged-cell value,
        # leaving following merchant rows blank. Carry the immediately preceding
        # valid transaction date within the same table only.
        if used_date and re.match(r"20\d{2}", used_date):
            last_used_date = used_date
        elif not used_date and merchant and last_used_date:
            used_date = last_used_date
            date_inferred = True
        if not merchant and amount is None:
            continue
        # Skip structural/header/subtotal rows that carry a numeric amount but
        # have neither a transaction date nor a merchant. These occur in some
        # Suwon committee sheets and are not expense events.
        if not merchant and not used_date:
            continue
        # Skip obvious subtotal/footer rows. Some councils put "합계" or
        # "계" directly in the date column, so a truthy used_date is not enough
        # to distinguish a transaction from a layout/footer row.
        joined = " ".join(clean_text(x) for x in row[:8])
        structural_date = bool(re.fullmatch(r"(?:합계|총계|누계|계)", used_date or ""))
        if structural_date or (any(k in joined for k in ("합계", "총계", "누계")) and not used_date):
            continue
        purpose = clean_text(cell(row, mapping, "purpose"))
        raw = {
            "region": source_meta["region"],
            "jurisdiction": source_meta["jurisdiction"],
            "institution": source_meta["institution"],
            "source_key": source_meta["source"],
            "source_post_url": source_meta["post_url"],
            "source_attachment_url": source_meta["attachment_url"],
            "source_attachment_name": source_meta["attachment_name"],
            "source_period": source_meta.get("period"),
            "source_sheet": sheet_name,
            "source_row": ri,
            "used_date": used_date,
            "date_inferred_from_previous_row": date_inferred,
            "used_time": clean_text(cell(row, mapping, "time")),
            "role": resolve_role(
                cell(row, mapping, "role"),
                sheet_name,
                section_role or source_meta.get("default_role"),
                purpose=purpose,
            ),
            "merchant": merchant,
            "address": clean_text(cell(row, mapping, "address")),
            "purpose": purpose,
            "people": parse_people(cell(row, mapping, "people")),
            "amount": amount,
            "payment_method": clean_text(cell(row, mapping, "method")),
            "parse_confidence": "high" if {"date", "merchant", "amount"}.issubset(mapping) else "medium",
        }
        raw["row_id"] = hashlib.sha256(
            "|".join(str(raw.get(k, "")) for k in ("institution", "used_date", "role", "merchant", "amount", "source_sheet", "source_row")).encode("utf-8")
        ).hexdigest()[:20]
        out.append(raw)
    info = {"sheet": sheet_name, "status": "OK", "header_row": hi + 1, "header_score": score, "matched": sorted(matched), "mapping": mapping, "section_role": section_role, "parsed_rows": len(out)}
    return out, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="goyang")
    args = ap.parse_args()
    source_discovery = REPORTS / f"capital-backfill-discovery-{args.source}.json"
    discovery_path = source_discovery if source_discovery.exists() else DISCOVERY
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    posts = [p for p in discovery.get("posts", []) if p.get("source") == args.source and p.get("post_url")]
    if not posts:
        raise SystemExit(f"no discovered posts for source={args.source}")

    all_rows, files, errors = [], [], []
    for post in posts:
        for att in post.get("attachments", []):
            url = att.get("url") or ""
            if not url:
                continue
            name = clean_text(att.get("text")) or url.rsplit("/", 1)[-1]
            try:
                blob = fetch_binary(url, post.get("post_url") or "")
                per_file = {"title": post.get("title"), "url": url, "name": name, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "sheets": []}
                carried_pdf_role = ""
                for sheet_name, rows in workbook_rows(blob, name):
                    page_role = infer_pdf_context_role(rows) if sheet_name.startswith("pdf-page-") else ""
                    if page_role:
                        carried_pdf_role = page_role
                    meta = {
                        "source": post["source"], "region": post["region"], "jurisdiction": post["jurisdiction"], "institution": post["institution"],
                        "post_url": post["post_url"], "attachment_url": url, "attachment_name": name, "period": post.get("period"),
                        "default_role": (
                            page_role
                            or carried_pdf_role
                            or infer_leadership_role(name)
                            or infer_leadership_role(post.get("title"))
                        ),
                    }
                    normalized, info = normalize_sheet(rows, sheet_name, meta)
                    if sheet_name.startswith("pdf-page-"):
                        info["pdf_page_role"] = page_role
                        info["carried_pdf_role"] = carried_pdf_role
                    per_file["sheets"].append(info)
                    all_rows.extend(normalized)
                files.append(per_file)
            except Exception as e:
                errors.append({"post": post.get("title"), "url": url, "error": f"{type(e).__name__}: {e}"})

    # Stable de-dupe across repeated publication/file discovery.
    unique = {r["row_id"]: r for r in all_rows}
    all_rows = sorted(unique.values(), key=lambda r: (r.get("used_date") or "", r.get("institution") or "", r.get("row_id")))
    payload = {
        "schema_version": 1,
        "source": args.source,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "row_count": len(all_rows),
        "rows": all_rows,
        "files": files,
        "errors": errors,
    }
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f"{args.source}_expense.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    by_role = Counter(r.get("role") or "(unknown)" for r in all_rows)
    by_year = Counter((r.get("used_date") or "")[:4] for r in all_rows if re.match(r"20\d{2}", r.get("used_date") or ""))
    report = REPORTS / f"{args.source}-ingestion.md"
    lines = [
        f"# {args.source} expense ingestion",
        "",
        f"- Normalized rows: **{len(all_rows)}**",
        f"- Source posts: **{len(posts)}**",
        f"- Downloaded files: **{len(files)}**",
        f"- Errors: **{len(errors)}**",
        "",
        "## Rows by year",
        "",
    ]
    for k, v in sorted(by_year.items()): lines.append(f"- {k}: {v}")
    lines += ["", "## Top roles / sheets", ""]
    for k, v in by_role.most_common(20): lines.append(f"- {k}: {v}")
    lines += ["", "## Files", ""]
    for f in files:
        lines.append(f"- `{f['name'][:120]}` — {f['bytes']:,} bytes — {sum(s.get('parsed_rows', 0) for s in f['sheets'])} rows")
        for s in f["sheets"]: lines.append(f"  - {s['sheet']}: {s['status']} / parsed {s.get('parsed_rows', 0)} / mapping {s.get('mapping', {})}")
    if errors:
        lines += ["", "## Errors", ""]
        for e in errors: lines.append(f"- {e['error']} — {e['url']}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"source": args.source, "rows": len(all_rows), "files": len(files), "errors": len(errors)}, ensure_ascii=False))
    print(out)
    if errors and not files:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
