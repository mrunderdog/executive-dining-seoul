#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import re
import urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"
UA = "ExecutiveDiningSeoul/2.2 (+https://github.com/mrunderdog/executive-dining-seoul)"
REPO_CONTENTS = "https://api.github.com/repos/OhmyNews/KA-money/contents?ref=master"
EXPECTED_MIN_TOTAL = 100_000
EXPECTED_MIN_PER_ASSEMBLY = 10_000

ALIASES = {
    "member": ["의원명", "국회의원명"],
    "party": ["당", "정당", "소속정당"],
    "district": ["지역명", "지역구", "선거구"],
    "date": ["연월일", "날짜", "지출일", "지출일자"],
    "purpose": ["내역", "지출내역", "내용", "사용내역"],
    "amount": ["지출액", "금액", "지출금액"],
    "merchant": ["사용처", "지출받은자", "지출처", "성명(법인,단체명)", "성명(법인·단체명)"],
    "category": ["분류 항목", "분류항목", "분류", "대분류", "중분류"],
}


def clean(v) -> str:
    return " ".join(str(v or "").replace("\n", " ").split()).strip()


def nh(v) -> str:
    return re.sub(r"[\s()\[\]·ㆍ._/\-]+", "", clean(v)).lower()


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def fetch_json(url: str):
    return json.loads(fetch(url).decode("utf-8"))


def discover_files() -> list[tuple[str, str, str]]:
    """Prefer the richer 2024 수입지출 files; fall back to the legacy export."""
    items = fetch_json(REPO_CONTENTS)
    out = []
    for assembly, token in (("21대", "2024_KAPF-21"), ("22대", "2024_KAPF-22")):
        matching = [x for x in items if x.get("type") == "file" and str(x.get("name", "")).startswith(token) and str(x.get("name", "")).lower().endswith(".xlsx")]
        matching.sort(key=lambda x: ("수입지출" not in str(x.get("name", "")), len(str(x.get("name", "")))))
        if not matching:
            raise RuntimeError(f"No 2024 source workbook found for {assembly}")
        for x in matching:
            url = x.get("download_url")
            if url:
                out.append((assembly, str(x.get("name")), url))
    return out


def pdate(v) -> str:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, (int, float)) and 20_000 < float(v) < 80_000:
        # Excel serial date, 1899-12-30 convention used by modern Excel/openpyxl.
        try:
            from datetime import timedelta
            return (date(1899, 12, 30) + timedelta(days=int(v))).isoformat()
        except Exception:
            pass
    s = clean(v)
    m = re.search(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass
    return s


def amount(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return int(round(v))
    s = re.sub(r"[^0-9.-]", "", clean(v))
    try:
        return int(round(float(s))) if s else None
    except ValueError:
        return None


def row_mapping(row) -> dict:
    mp = {}
    for j, c in enumerate(row):
        x = nh(c)
        if not x:
            continue
        for field, aliases in ALIASES.items():
            if field in mp:
                continue
            if any(nh(a) == x or nh(a) in x for a in aliases):
                mp[field] = j
    return mp


def find_header(ws):
    best = (-1, -1, {})
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=min(ws.max_row or 100, 120), values_only=True), start=1):
        mp = row_mapping(row)
        required = sum(k in mp for k in ("member", "date", "purpose", "amount", "merchant"))
        score = required * 10 + len(mp)
        if score > best[0]:
            best = (score, i, mp)
    return best if all(k in best[2] for k in ("member", "date", "amount", "merchant")) else None


def cell(row, mp, key):
    i = mp.get(key)
    return row[i] if i is not None and i < len(row) else None


def parse_workbook(blob: bytes, assembly: str, source_name: str, source_url: str):
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
    parsed_rows = []
    sheets = []
    for ws in wb.worksheets:
        h = find_header(ws)
        if not h:
            sheets.append({"sheet": ws.title, "max_row": ws.max_row, "status": "NO_HEADER", "parsed_rows": 0})
            continue
        _, header_row, mp = h
        count = 0
        for ri, row in enumerate(ws.iter_rows(min_row=header_row + 1, values_only=True), start=header_row + 1):
            member = clean(cell(row, mp, "member"))
            merchant = clean(cell(row, mp, "merchant"))
            amt = amount(cell(row, mp, "amount"))
            used_date = pdate(cell(row, mp, "date"))
            purpose = clean(cell(row, mp, "purpose"))
            if not member or (not merchant and amt is None):
                continue
            if member in {"의원명", "합계", "총계"}:
                continue
            r = {
                "assembly": assembly,
                "member": member,
                "party": clean(cell(row, mp, "party")),
                "district": clean(cell(row, mp, "district")),
                "used_date": used_date,
                "purpose": purpose,
                "amount": amt,
                "merchant": merchant,
                "category": clean(cell(row, mp, "category")),
                "cohort": "national_legislator",
                "source_url": source_url,
                "source_file": source_name,
                "source_sheet": ws.title,
                "source_row": ri,
            }
            r["row_id"] = hashlib.sha256(
                "|".join(str(r.get(k, "")) for k in ("assembly", "member", "used_date", "merchant", "amount", "source_file", "source_sheet", "source_row")).encode("utf-8")
            ).hexdigest()[:20]
            parsed_rows.append(r)
            count += 1
        sheets.append({"sheet": ws.title, "max_row": ws.max_row, "status": "OK", "header_row": header_row, "mapping": mp, "parsed_rows": count})
    return parsed_rows, sheets


def main():
    RAW_DIR.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    errors = []
    files = []
    all_rows = []

    discovered = discover_files()
    by_assembly: dict[str, list[tuple[str, str]]] = {"21대": [], "22대": []}
    for assembly, name, url in discovered:
        by_assembly[assembly].append((name, url))

    for assembly in ("21대", "22대"):
        best_rows = []
        best_info = None
        for name, url in by_assembly[assembly]:
            try:
                blob = fetch(url)
                rows, sheets = parse_workbook(blob, assembly, name, url)
                info = {"assembly": assembly, "name": name, "url": url, "bytes": len(blob), "parsed_rows": len(rows), "sheets": sheets}
                files.append(info)
                if len(rows) > len(best_rows):
                    best_rows = rows
                    best_info = info
                if len(rows) >= EXPECTED_MIN_PER_ASSEMBLY:
                    break
            except Exception as e:
                errors.append({"assembly": assembly, "name": name, "url": url, "error": f"{type(e).__name__}: {e}"})
        if best_info is None:
            errors.append({"assembly": assembly, "error": "no workbook could be parsed"})
        all_rows.extend(best_rows)

    unique = {r["row_id"]: r for r in all_rows}
    rows = sorted(unique.values(), key=lambda r: (r.get("used_date") or "", r.get("member") or "", r["row_id"]))

    payload = {
        "schema_version": 2,
        "source": "OhmyNews/KA-money",
        "upstream": "Central Election Commission political-fund accounting reports obtained via information disclosure",
        "year": 2024,
        "row_count": len(rows),
        "rows": rows,
        "files": files,
        "errors": errors,
    }
    out = RAW_DIR / "national_legislator_2024_expense.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    md = [
        "# National legislator political-fund ingestion — 2024",
        "",
        "> Source lineage: Central Election Commission accounting reports → information-disclosure PDFs → OhmyNews/Kyunghyang/Newstapa OCR/normalization → this project.",
        "",
        f"- Rows: **{len(rows)}**",
        f"- Workbooks attempted: **{len(files)}**",
        f"- Errors: **{len(errors)}**",
        "",
        "## Workbook diagnostics",
        "",
    ]
    for f in files:
        md.append(f"- {f['assembly']} `{f['name']}`: {f['parsed_rows']:,} rows")
        for s in f.get("sheets", []):
            md.append(f"  - {s['sheet']}: {s.get('status')} / {s.get('parsed_rows', 0):,} rows / header={s.get('header_row', '-')}")
    if errors:
        md += ["", "## Errors", ""]
        for e in errors:
            md.append(f"- {e}")
    (REPORTS / "national-legislator-ingestion.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"rows": len(rows), "files": len(files), "errors": len(errors)}, ensure_ascii=False))
    if len(rows) < EXPECTED_MIN_TOTAL:
        raise SystemExit(f"Legislator ingestion sanity gate failed: parsed {len(rows):,} rows; expected at least {EXPECTED_MIN_TOTAL:,} from 2024 21st+22nd Assembly workbooks")


if __name__ == "__main__":
    main()
