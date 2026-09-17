#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import re
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"
UA = "ExecutiveDiningSeoul/2.4 (+https://github.com/mrunderdog/executive-dining-seoul)"

# OhmyNews documents the legacy 2024 exports as:
# 총연번, 의원번호, 의원명, 당, 당ID, 지역명, 연월일, 내역, 지출액, 사용처, 분류 항목
FILES = [
    ("21대", "2024_KAPF-21.xlsx", "https://raw.githubusercontent.com/OhmyNews/KA-money/master/2024_KAPF-21.xlsx", 64_391),
    ("22대", "2024_KAPF-22.xlsx", "https://raw.githubusercontent.com/OhmyNews/KA-money/master/2024_KAPF-22.xlsx", 70_652),
]

# Detailed 2024 workbooks are probed only for merchant metadata such as an address.
# Their layout is not assumed: headers are detected conservatively and diagnostics are
# written even when no usable merchant-address columns exist.
RICH_FILES = [
    ("21대", "2024_KAPF-21_수입지출.xlsx", "https://raw.githubusercontent.com/OhmyNews/KA-money/master/2024_KAPF-21_%E1%84%89%E1%85%AE%E1%84%8B%E1%85%B5%E1%86%B8%E1%84%8C%E1%85%B5%E1%84%8E%E1%85%AE%E1%86%AF.xlsx"),
    ("22대", "2024_KAPF-22_수입지출.xlsx", "https://raw.githubusercontent.com/OhmyNews/KA-money/master/2024_KAPF-22_%E1%84%89%E1%85%AE%E1%84%8B%E1%85%B5%E1%86%B8%E1%84%8C%E1%85%B5%E1%84%8E%E1%85%AE%E1%86%AF.xlsx"),
]
EXPECTED_MIN_TOTAL = 130_000

COL = {
    "serial": 0,
    "member_id": 1,
    "member": 2,
    "party": 3,
    "party_id": 4,
    "district": 5,
    "date": 6,
    "purpose": 7,
    "amount": 8,
    "merchant": 9,
    "category": 10,
}


def clean(v) -> str:
    return " ".join(str(v or "").replace("\n", " ").split()).strip()


def header_norm(v) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", clean(v).lower())


def merchant_norm(v) -> str:
    s = clean(v).lower()
    s = re.sub(r"^(?:주식회사|\(주\)|㈜|유한회사)\s*", "", s)
    return re.sub(r"[^0-9a-z가-힣]", "", s)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def parse_date(v) -> str:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, (int, float)) and 20_000 < float(v) < 80_000:
        try:
            return (date(1899, 12, 30) + timedelta(days=int(v))).isoformat()
        except Exception:
            return ""
    s = clean(v)
    m = re.search(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", s)
    if not m:
        m = re.search(r"\b(20\d{2})(\d{2})(\d{2})\b", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return ""
    return ""


def parse_amount(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return int(round(v))
    s = re.sub(r"[^0-9.-]", "", clean(v))
    try:
        return int(round(float(s))) if s else None
    except ValueError:
        return None


def val(row, key):
    i = COL[key]
    return row[i] if i < len(row) else None


def parse_sheet(ws, assembly: str, source_name: str, source_url: str):
    out = []
    carry = {"member_id": "", "member": "", "party": "", "party_id": "", "district": ""}
    nonempty = 0
    valid_2024 = 0
    for ri, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if not any(x not in (None, "") for x in row):
            continue
        nonempty += 1
        for k in carry:
            x = clean(val(row, k))
            if x and x not in {"의원번호", "의원명", "당", "당ID", "지역명"}:
                carry[k] = x

        used_date = parse_date(val(row, "date"))
        amt = parse_amount(val(row, "amount"))
        merchant = clean(val(row, "merchant"))
        purpose = clean(val(row, "purpose"))
        category = clean(val(row, "category"))
        if not used_date.startswith("2024-"):
            continue
        valid_2024 += 1
        if amt is None or not merchant or not carry["member"]:
            continue
        if merchant in {"사용처", "합계", "총계"}:
            continue

        r = {
            "assembly": assembly,
            "member_id": carry["member_id"],
            "member": carry["member"],
            "party": carry["party"],
            "party_id": carry["party_id"],
            "district": carry["district"],
            "used_date": used_date,
            "purpose": purpose,
            "amount": amt,
            "merchant": merchant,
            "address": "",
            "category": category,
            "cohort": "national_legislator",
            "source_url": source_url,
            "source_file": source_name,
            "source_sheet": ws.title,
            "source_row": ri,
        }
        r["row_id"] = hashlib.sha256(
            "|".join(str(r.get(k, "")) for k in ("assembly", "member_id", "member", "used_date", "merchant", "amount", "source_file", "source_sheet", "source_row")).encode("utf-8")
        ).hexdigest()[:20]
        out.append(r)

    return out, {"sheet": ws.title, "max_row": ws.max_row, "max_column": ws.max_column, "nonempty_rows": nonempty, "date_2024_rows": valid_2024, "parsed_rows": len(out)}


def find_rich_header(ws):
    merchant_terms = ("사용처", "지출받은자", "성명법인단체명", "법인단체명", "성명")
    address_terms = ("주소", "소재지", "사무소소재지")
    best = None
    for ri, row in enumerate(ws.iter_rows(min_row=1, max_row=min(ws.max_row or 80, 80), values_only=True), start=1):
        vals = [header_norm(x) for x in row]
        m = next((i for i, h in enumerate(vals) if any(term in h for term in merchant_terms)), None)
        a = next((i for i, h in enumerate(vals) if any(term in h for term in address_terms)), None)
        if m is not None and a is not None and m != a:
            score = sum(bool(x) for x in vals)
            if best is None or score > best[0]:
                best = (score, ri, m, a, [clean(x) for x in row])
    return best


def rich_address_map(openpyxl):
    addresses: dict[str, Counter] = defaultdict(Counter)
    diagnostics = []
    for assembly, name, url in RICH_FILES:
        try:
            blob = fetch(url)
            wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
            file_diag = {"assembly": assembly, "name": name, "bytes": len(blob), "sheets": []}
            for ws in wb.worksheets:
                found = find_rich_header(ws)
                if not found:
                    file_diag["sheets"].append({"sheet": ws.title, "status": "NO_MERCHANT_ADDRESS_HEADER", "rows": ws.max_row, "cols": ws.max_column})
                    continue
                _, header_row, merchant_col, address_col, headers = found
                matched = 0
                for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
                    merchant = clean(row[merchant_col] if merchant_col < len(row) else None)
                    address = clean(row[address_col] if address_col < len(row) else None)
                    key = merchant_norm(merchant)
                    if len(key) < 2 or len(address) < 5:
                        continue
                    # Require an address-looking token to avoid treating another free-text field as an address.
                    if not re.search(r"(?:서울|경기|인천|부산|대구|대전|광주|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주|\b\S+[시군구]\b|로\s*\d|길\s*\d|동\s*\d)", address):
                        continue
                    addresses[key][address] += 1
                    matched += 1
                file_diag["sheets"].append({
                    "sheet": ws.title,
                    "status": "OK",
                    "rows": ws.max_row,
                    "cols": ws.max_column,
                    "header_row": header_row,
                    "merchant_col": merchant_col + 1,
                    "address_col": address_col + 1,
                    "headers": headers[:30],
                    "address_rows": matched,
                })
            diagnostics.append(file_diag)
        except Exception as e:
            diagnostics.append({"assembly": assembly, "name": name, "error": f"{type(e).__name__}: {e}"})
    return addresses, diagnostics


def main():
    import openpyxl

    RAW_DIR.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    all_rows = []
    files = []
    errors = []

    for assembly, name, url, documented_count in FILES:
        try:
            blob = fetch(url)
            wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
            workbook_rows = []
            sheets = []
            for ws in wb.worksheets:
                rows, diag = parse_sheet(ws, assembly, name, url)
                workbook_rows.extend(rows)
                sheets.append(diag)
            files.append({
                "assembly": assembly,
                "name": name,
                "url": url,
                "bytes": len(blob),
                "documented_count": documented_count,
                "parsed_rows": len(workbook_rows),
                "sheets": sheets,
            })
            all_rows.extend(workbook_rows)
        except Exception as e:
            errors.append({"assembly": assembly, "name": name, "url": url, "error": f"{type(e).__name__}: {e}"})

    address_map, rich_diagnostics = rich_address_map(openpyxl)
    enriched = 0
    for r in all_rows:
        choices = address_map.get(merchant_norm(r.get("merchant")))
        if choices:
            r["address"] = choices.most_common(1)[0][0]
            enriched += 1

    unique = {r["row_id"]: r for r in all_rows}
    rows = sorted(unique.values(), key=lambda r: (r.get("used_date") or "", r.get("member") or "", r["row_id"]))

    payload = {
        "schema_version": 4,
        "source": "OhmyNews/KA-money",
        "upstream": "Central Election Commission political-fund accounting reports obtained via information disclosure",
        "year": 2024,
        "row_count": len(rows),
        "address_enriched_rows": enriched,
        "address_merchant_count": len(address_map),
        "rows": rows,
        "files": files,
        "rich_files": rich_diagnostics,
        "errors": errors,
    }
    (RAW_DIR / "national_legislator_2024_expense.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    md = [
        "# National legislator political-fund ingestion — 2024",
        "",
        "> Source lineage: Central Election Commission accounting reports → information-disclosure PDFs → OhmyNews/Kyunghyang/Newstapa OCR/normalization → this project.",
        "",
        f"- Rows: **{len(rows):,}**",
        f"- Workbooks: **{len(files)}**",
        f"- Merchant keys with address metadata from detailed workbooks: **{len(address_map):,}**",
        f"- Legacy spending rows enriched with an address: **{enriched:,}**",
        f"- Errors: **{len(errors)}**",
        "",
        "## Workbook diagnostics",
        "",
    ]
    for f in files:
        md.append(f"- {f['assembly']} `{f['name']}`: parsed **{f['parsed_rows']:,}** / documented **{f['documented_count']:,}**")
        for s in f.get("sheets", []):
            md.append(f"  - `{s['sheet']}` rows={s['max_row']:,}, cols={s['max_column']}, 2024-date={s['date_2024_rows']:,}, parsed={s['parsed_rows']:,}")
    md += ["", "## Detailed workbook address probe", ""]
    for f in rich_diagnostics:
        if f.get("error"):
            md.append(f"- {f.get('assembly')} `{f.get('name')}`: ERROR {f.get('error')}")
            continue
        md.append(f"- {f.get('assembly')} `{f.get('name')}`")
        for s in f.get("sheets", []):
            md.append(f"  - `{s.get('sheet')}`: {s.get('status')} / address rows={s.get('address_rows', 0):,} / cols={s.get('cols', 0)}")
            if s.get('status') == 'OK':
                md.append(f"    - header row {s.get('header_row')}, merchant col {s.get('merchant_col')}, address col {s.get('address_col')}: {s.get('headers')}")
    if errors:
        md += ["", "## Errors", ""]
        for e in errors:
            md.append(f"- {e}")
    (REPORTS / "national-legislator-ingestion.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"rows": len(rows), "files": len(files), "errors": len(errors), "address_merchants": len(address_map), "address_rows": enriched}, ensure_ascii=False))
    if len(rows) < EXPECTED_MIN_TOTAL:
        raise SystemExit(
            f"Legislator ingestion sanity gate failed: parsed {len(rows):,} rows; "
            f"documented legacy exports total {sum(x[3] for x in FILES):,}. "
            "See reports/national-legislator-ingestion.md diagnostics."
        )


if __name__ == "__main__":
    main()
