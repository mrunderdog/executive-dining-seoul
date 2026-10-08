"""Table-accurate Gyeonggi education leadership PDF adapter.

GOE's landscape PDF uses a real 8-column table. The general layout text
extractor can mistake '집행시간' for the only time column and drop every row;
pdfplumber's structural table avoids cross-column merchant/amount shifts.
"""
from __future__ import annotations
import io
import re
import urllib.request
from datetime import date

def clean(v: object) -> str:
    return " ".join(str(v or "").replace("\n", " ").split())

def normalize_table(table: list[list], source_url: str, page_no: int, table_no: int) -> list[dict]:
    if not table:
        return []
    header = [re.sub(r"\s+", "", clean(c)) for c in table[0]]
    indexes = {
        "date": next((i for i, h in enumerate(header) if "집행일" in h), None),
        "time": next((i for i, h in enumerate(header) if "집행시간" in h), None),
        "purpose": next((i for i, h in enumerate(header) if "적요" in h), None),
        "amount": next((i for i, h in enumerate(header) if h in ("액", "금액", "집행금액")), None),
        "merchant": next((i for i, h in enumerate(header) if "실거래처" in h or "사용처" in h), None),
        "target": next((i for i, h in enumerate(header) if "집행대상" in h), None),
        "method": next((i for i, h in enumerate(header) if "집행방법" in h), None),
    }
    if any(indexes[k] is None for k in ("date", "amount", "merchant")):
        return []
    def val(row, key):
        i = indexes[key]
        return clean(row[i]) if i is not None and i < len(row) else ""
    rows=[]
    last_date = ""
    for ri, row in enumerate(table[1:], 2):
        raw_date = val(row, "date")
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", raw_date):
            try:
                date.fromisoformat(raw_date)
                last_date=raw_date
            except ValueError:
                continue
        elif raw_date:
            last_date=""
            continue
        if not last_date:
            continue
        merchant=val(row, "merchant")
        if not merchant or merchant in {"-", "합계", "총계"}:
            continue
        amount_text=val(row, "amount")
        try: amount=int(re.sub(r"[^0-9]", "", amount_text))
        except ValueError: continue
        if amount <= 0:
            continue
        target=val(row,"target")
        people=re.search(r"(\d+)\s*명", target)
        rows.append({
            "used_date": last_date, "used_time": val(row, "time"),
            "purpose": val(row, "purpose"), "merchant": merchant,
            "amount": amount, "people": int(people.group(1)) if people else 0,
            "target": target, "payment_method": val(row, "method"),
            "source_url": source_url, "source_sheet": f"pdf-p{page_no}-t{table_no}",
            "source_row": ri,
        })
    return rows

def parse(url: str, referer: str = "") -> tuple[list[dict], dict, str | None]:
    try:
        import pdfplumber
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0",
                                "Referer":referer or url,"Accept":"application/pdf"})
        with urllib.request.urlopen(req,timeout=20) as response:
            blob=response.read(15_000_000)
        if not blob.startswith(b"%PDF"):
            raise ValueError("not a PDF response")
        parsed=[]
        sheets=[]
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            for pi, page in enumerate(pdf.pages,1):
                for ti, table in enumerate(page.extract_tables(),1):
                    found=normalize_table(table or [],url,pi,ti)
                    parsed.extend(found)
                    sheets.append({"sheet":f"p{pi}-t{ti}","status":"OK" if found else "NO_ROWS","parsed_rows":len(found)})
        info={"url":url,"bytes":len(blob),"sheets":sheets,"source_parser":"gyeonggi_education_pdf"}
        return parsed,info,None
    except Exception as exc:
        return [],{},f"{type(exc).__name__}: {str(exc)[:250]}"
