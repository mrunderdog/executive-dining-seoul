#!/usr/bin/env python3
"""Download and normalize council expense spreadsheets discovered from official sources.

Stage 1 supports Goyang's quarterly XLS/XLSX attachments. Output is a raw canonical layer,
NOT the published restaurant ranking. Publication remains gated by entity matching/scoring.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import urllib.request
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
RAW_DIR = ROOT / "data" / "raw"
DISCOVERY = REPORTS / "capital-backfill-discovery.json"
UA = "ExecutiveDiningSeoul/1.0 (+https://github.com/mrunderdog/executive-dining-seoul)"

ALIASES = {
    "date": ["사용일", "사용일자", "집행일", "집행일자", "일자", "사용일시", "집행일시"],
    "time": ["사용시간", "집행시간", "시간"],
    "merchant": ["집행장소", "사용처", "사용장소", "장소", "업소명", "상호", "가맹점명"],
    "address": ["주소", "소재지", "집행장소주소", "사용처주소"],
    "purpose": ["집행목적", "사용목적", "목적", "내용", "적요"],
    "people": ["인원", "참석인원", "대상인원", "사용인원"],
    "amount": ["금액", "집행금액", "사용금액", "결제금액", "지출금액"],
    "role": ["사용자", "사용자명", "직책", "집행자", "부서", "구분"],
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


def fetch_binary(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def workbook_rows(blob: bytes, filename: str):
    lower = filename.lower()
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
    for idx, cell in enumerate(row):
        c = norm_header(cell)
        if not c:
            continue
        for field, aliases in ALIASES.items():
            if field in result: continue
            if any(norm_header(a) == c or norm_header(a) in c for a in aliases):
                result[field] = idx
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

def normalize_sheet(rows, sheet_name, source_meta):
    found = find_header(rows)
    if not found:
        return [], {"sheet": sheet_name, "status": "NO_HEADER", "rows": len(rows)}
    score, hi, matched = found
    mapping = map_columns(rows[hi])
    out = []
    blank_run = 0
    for ri, row in enumerate(rows[hi + 1:], start=hi + 2):
        if not any(clean_text(x) for x in row):
            blank_run += 1
            if blank_run >= 8 and out: break
            continue
        blank_run = 0
        merchant = clean_text(cell(row, mapping, "merchant"))
        amount = parse_amount(cell(row, mapping, "amount"))
        used_date = parse_date(cell(row, mapping, "date"))
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
            "used_time": clean_text(cell(row, mapping, "time")),
            "role": clean_text(cell(row, mapping, "role")) or source_meta.get("default_role") or sheet_name,
            "merchant": merchant,
            "address": clean_text(cell(row, mapping, "address")),
            "purpose": clean_text(cell(row, mapping, "purpose")),
            "people": parse_people(cell(row, mapping, "people")),
            "amount": amount,
            "payment_method": clean_text(cell(row, mapping, "method")),
            "parse_confidence": "high" if {"date", "merchant", "amount"}.issubset(mapping) else "medium",
        }
        raw["row_id"] = hashlib.sha256(
            "|".join(str(raw.get(k, "")) for k in ("institution", "used_date", "role", "merchant", "amount", "source_sheet", "source_row")).encode("utf-8")
        ).hexdigest()[:20]
        out.append(raw)
    info = {"sheet": sheet_name, "status": "OK", "header_row": hi + 1, "header_score": score, "matched": sorted(matched), "mapping": mapping, "parsed_rows": len(out)}
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
                blob = fetch_binary(url)
                per_file = {"title": post.get("title"), "url": url, "name": name, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "sheets": []}
                for sheet_name, rows in workbook_rows(blob, name):
                    meta = {
                        "source": post["source"], "region": post["region"], "jurisdiction": post["jurisdiction"], "institution": post["institution"],
                        "post_url": post["post_url"], "attachment_url": url, "attachment_name": name, "period": post.get("period"),
                        "default_role": infer_leadership_role(name) or infer_leadership_role(post.get("title")),
                    }
                    normalized, info = normalize_sheet(rows, sheet_name, meta)
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
