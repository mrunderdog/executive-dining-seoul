#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"

SERVICE_NAME = "odExpense"
BASE_URL = "http://openapi.seoul.go.kr:8088"
PAGE_SIZE = 1000
SOURCE_PAGE = "https://data.seoul.go.kr/dataList/OA-22156/S/1/datasetView.do"
DEFAULT_SINCE = "2024-12"

FIELD_ALIASES = {
    "department": ("DEPT_NM_FULL", "DEPT_NM"),
    "used_at": ("EXEC_DT", "EXEC_DATE", "USE_DT"),
    "merchant": ("EXEC_LOC", "USE_PLACE", "EXEC_PLACE"),
    "purpose": ("EXEC_PURPOSE", "PURPOSE"),
    "target": ("TARGET_NM", "TARGET"),
    "amount": ("EXEC_AMOUNT", "AMOUNT"),
    "payment_method": ("PAYMENT_METHOD", "PAYMENT_MTHD_NM", "EXEC_METHOD"),
    "budget_item": ("EXPENSE_TYPE", "BUDGET_NM", "BUDGET_ITEM"),
    "document_url": ("DOC_URL", "DOCUMENT_URL", "URL"),
    "document_id": ("DOC_ID", "DOC_NO", "DOC_SEQ"),
    "year": ("EXEC_YEAR", "YEAR"),
    "month": ("EXEC_MONTH", "MONTH"),
}


def text(v) -> str:
    return " ".join(str(v or "").replace("\n", " ").split()).strip()


def row_get(row: dict, field: str) -> str:
    for key in FIELD_ALIASES[field]:
        if key in row and text(row.get(key)):
            return text(row.get(key))
    return ""


def parse_amount(v) -> int | None:
    s = re.sub(r"[^0-9.-]", "", text(v))
    if not s:
        return None
    try:
        return int(round(float(s)))
    except ValueError:
        return None


def parse_people(target: str) -> int | None:
    s = text(target)
    if not s:
        return None
    m = re.search(r"외\s*(\d+)\s*명", s)
    if m:
        return int(m.group(1)) + 1
    m = re.search(r"(?:등\s*)?(\d+)\s*(?:명|인)\b", s)
    if m:
        return int(m.group(1))
    return None


def parse_datetime(v: str) -> tuple[str, str]:
    s = text(v)
    m = re.search(
        r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})"
        r"(?:[일T\s]+(\d{1,2})[:시](\d{1,2})?)?",
        s,
    )
    if not m:
        return "", ""
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return "", ""
    hh = m.group(4)
    mm = m.group(5)
    t = f"{int(hh):02d}:{int(mm or 0):02d}" if hh is not None else ""
    return d, t


def split_place(v: str) -> tuple[str, str]:
    s = text(v)
    if not s:
        return "", ""
    m = re.match(r"^(.*?)[（(]([^()（）]+)[)）]\s*$", s)
    if not m:
        return s, ""
    name, hint = text(m.group(1)), text(m.group(2))
    address_tokens = ("서울", "경기", "인천", "부산", "대구", "대전", "광주", "울산",
                      "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
                      "구 ", "시 ", "군 ", "로 ", "길 ", "동 ", "대로")
    if any(tok in hint for tok in address_tokens):
        return name or s, hint
    return s, ""


def ym_value(s: str) -> tuple[int, int]:
    y, m = s.split("-")
    return int(y), int(m)


def month_in_range(used_date: str, since: tuple[int, int], until: tuple[int, int]) -> bool:
    m = re.match(r"(20\d{2})-(\d{2})-\d{2}", used_date or "")
    if not m:
        return False
    ym = (int(m.group(1)), int(m.group(2)))
    return since <= ym <= until


def fetch_page(api_key: str, start: int, end: int, service_name: str) -> tuple[list[dict], int | None]:
    quoted_key = urllib.parse.quote(api_key, safe="")
    url = f"{BASE_URL}/{quoted_key}/json/{service_name}/{start}/{end}/"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ExecutiveDiningSeoul/2.0 (+https://github.com/mrunderdog/executive-dining-seoul)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.loads(r.read().decode("utf-8"))
    svc = payload.get(service_name)
    if not isinstance(svc, dict):
        result = payload.get("RESULT") or {}
        raise RuntimeError(f"Seoul API error: {result.get('MESSAGE') or str(payload)[:300]}")
    rows = svc.get("row") or []
    total = svc.get("list_total_count")
    return rows, int(total) if isinstance(total, (int, float, str)) and str(total).isdigit() else None


def normalize_row(row: dict, since: tuple[int, int], until: tuple[int, int]) -> dict:
    used_date, used_time = parse_datetime(row_get(row, "used_at"))
    merchant, address = split_place(row_get(row, "merchant"))
    amount = parse_amount(row_get(row, "amount"))
    department = row_get(row, "department")
    purpose = row_get(row, "purpose")
    target = row_get(row, "target")
    document_url = row_get(row, "document_url")
    document_id = row_get(row, "document_id")

    normalized = {
        "region": "서울",
        "jurisdiction": "서울특별시",
        "institution": "서울특별시 본청",
        "jurisdiction_level": "regional_executive",
        "source_family": "executive_government",
        "source_key": "seoul_city_hall",
        "source_dataset_url": SOURCE_PAGE,
        "source_document_url": document_url,
        "source_document_id": document_id,
        "department": department,
        "role": department,
        "used_date": used_date,
        "used_time": used_time,
        "merchant": merchant,
        "address": address,
        "purpose": purpose,
        "target": target,
        "people": parse_people(target),
        "amount": amount,
        "payment_method": row_get(row, "payment_method"),
        "budget_item": row_get(row, "budget_item"),
        "date_quality": "in_period" if month_in_range(used_date, since, until) else ("parsed_outside_period" if used_date else "unparsed"),
    }
    identity = "|".join(
        str(normalized.get(k) or "")
        for k in ("institution", "department", "used_date", "used_time", "merchant", "amount", "purpose", "document_id")
    )
    normalized["row_id"] = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return normalized


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Seoul HQ business-promotion expenses from OA-22156 / odExpense.")
    ap.add_argument("--since", default=DEFAULT_SINCE, help="YYYY-MM inclusive")
    ap.add_argument("--until", default=datetime.now().strftime("%Y-%m"), help="YYYY-MM inclusive")
    ap.add_argument("--service", default=os.environ.get("SEOUL_SERVICE_NAME", SERVICE_NAME))
    ap.add_argument("--max-pages", type=int, default=0, help="0 = all pages")
    args = ap.parse_args()

    api_key = os.environ.get("SEOUL_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "SEOUL_API_KEY is required. Add it as a GitHub Actions secret or environment variable. "
            "Dataset: OA-22156; service: odExpense."
        )

    since, until = ym_value(args.since), ym_value(args.until)
    all_rows: list[dict] = []
    total_count = None
    start = 1
    page_no = 0

    while True:
        end = start + PAGE_SIZE - 1
        rows, total = fetch_page(api_key, start, end, args.service)
        page_no += 1
        if total_count is None and total is not None:
            total_count = total
        if not rows:
            break
        all_rows.extend(normalize_row(r, since, until) for r in rows)
        if len(rows) < PAGE_SIZE:
            break
        if args.max_pages and page_no >= args.max_pages:
            break
        start += PAGE_SIZE

    unique = {r["row_id"]: r for r in all_rows}
    rows = sorted(unique.values(), key=lambda r: (r.get("used_date") or "", r.get("department") or "", r["row_id"]))

    valid_dates = [r for r in rows if r.get("used_date")]
    in_period = [r for r in rows if r.get("date_quality") == "in_period"]
    merchant_rows = [r for r in in_period if r.get("merchant")]
    amount_rows = [r for r in in_period if isinstance(r.get("amount"), int) and r["amount"] >= 0]

    payload = {
        "schema_version": 1,
        "source": "seoul_city_hall",
        "service_name": args.service,
        "dataset": "OA-22156",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "since": args.since,
        "until": args.until,
        "api_total_count": total_count,
        "row_count": len(rows),
        "raw_quality": {
            "valid_date_coverage": round(len(valid_dates) / len(rows), 4) if rows else 0,
            "in_period_rows": len(in_period),
            "merchant_coverage_in_period": round(len(merchant_rows) / len(in_period), 4) if in_period else 0,
            "amount_coverage_in_period": round(len(amount_rows) / len(in_period), 4) if in_period else 0,
        },
        "rows": rows,
    }

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / "seoul_city_hall_expense.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    by_month = Counter((r.get("used_date") or "")[:7] for r in in_period if r.get("used_date"))
    by_department = Counter(r.get("department") or "(unknown)" for r in in_period)
    report = REPORTS / "seoul-city-hall-ingestion.md"
    lines = [
        "# Seoul City Hall expense ingestion",
        "",
        f"- Dataset: OA-22156 / `{args.service}`",
        f"- Requested period: **{args.since} ~ {args.until}**",
        f"- API total count: **{total_count if total_count is not None else 'unknown'}**",
        f"- Normalized rows: **{len(rows)}**",
        f"- In-period rows: **{len(in_period)}**",
        f"- Valid-date coverage: **{payload['raw_quality']['valid_date_coverage']:.1%}**",
        f"- Merchant coverage (in period): **{payload['raw_quality']['merchant_coverage_in_period']:.1%}**",
        f"- Amount coverage (in period): **{payload['raw_quality']['amount_coverage_in_period']:.1%}**",
        "",
        "## Rows by month",
        "",
    ]
    for k, v in sorted(by_month.items()):
        lines.append(f"- {k}: {v}")
    lines += ["", "## Top departments", ""]
    for k, v in by_department.most_common(30):
        lines.append(f"- {k}: {v}")
    lines += [
        "",
        "> Raw ingestion only. Restaurants are not published until meal filtering, entity matching, geocoding and the publication gate pass.",
        "",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "source": "seoul_city_hall",
        "rows": len(rows),
        "in_period": len(in_period),
        "api_total_count": total_count,
        "quality": payload["raw_quality"],
    }, ensure_ascii=False))
    print(out)


if __name__ == "__main__":
    main()
