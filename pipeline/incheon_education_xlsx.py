"""Native Incheon Education Office XLSX parser.

Official forms call the date column '결제일', sometimes using Excel datetimes
and sometimes dotted Korean dates. The shared parser does not map this field.
"""
from __future__ import annotations
import io
import re
import urllib.request
from datetime import date, datetime

def text(v):
    return " ".join(str(v or "").replace("\n", " ").split())

def parse_day(value):
    if isinstance(value, datetime):
        day=value.date()
    elif isinstance(value, date):
        day=value
    else:
        m=re.search(r"(20\d{2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})",text(value))
        if not m:
            return ""
        try: day=date(*map(int,m.groups()))
        except ValueError: return ""
    if not (date(2000,1,1) <= day <= date.today()):
        return ""
    return day.isoformat()

def normalize_rows(rows, source_url, sheet):
    out=[]
    for hi,row in enumerate(rows[:25]):
        hdr=[re.sub(r"\s+", "", text(x)) for x in row]
        fields = {
            "date": ("결제일","사용일자","집행일","사용일"),
            "merchant": ("장소","사용처","집행장소"),
            "amount": ("집행금액","결제금액","지출금액","금액"),
            "purpose": ("집행내용","내용","사용목적","집행목적"),
            "target": ("집행대상","대상","참석자"),
            "method": ("집행방법","결제방법","결제수단"),
        }
        idx = {key:next((i for i,v in enumerate(hdr) if v in names),None) for key,names in fields.items()}
        if any(idx[k] is None for k in ("date","merchant","amount")):
            continue
        def get(r,k):
            ix=idx[k];return r[ix] if ix is not None and ix < len(r) else None
        for ri,r in enumerate(rows[hi+1:],hi+2):
            d=parse_day(get(r,"date"))
            merchant=text(get(r,"merchant"))
            try:amount=int(float(str(get(r,"amount")).replace(",","")))
            except (ValueError,TypeError): continue
            if not d or not merchant or amount <= 0 or merchant in {"-","해당없음","미상"}:
                continue
            target=text(get(r,"target"))
            p=re.search(r"총\s*(\d+)\s*명",target)
            if not p:p=re.search(r"(\d+)\s*명",target)
            out.append({
                "used_date":d,"used_time":"","merchant":merchant,"amount":amount,
                "purpose":text(get(r,"purpose")),"target":target,
                "people":int(p.group(1)) if p else 0,
                "payment_method":text(get(r,"method")),
                "source_url":source_url,"source_sheet":sheet,"source_row":ri,
            })
        return out
    return []

def parse(url,referer=""):
    try:
        import openpyxl
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0",
                                  "Referer":referer or url})
        with urllib.request.urlopen(req,timeout=20) as response:
            blob=response.read(15_000_000)
        wb=openpyxl.load_workbook(io.BytesIO(blob),read_only=True,data_only=True)
        out=[];sheets=[]
        for ws in wb.worksheets:
            parsed=normalize_rows(list(ws.iter_rows(values_only=True)),url,ws.title)
            out.extend(parsed)
            sheets.append({"sheet":ws.title,"status":"OK" if parsed else "NO_ROWS","parsed_rows":len(parsed)})
        return out,{"url":url,"bytes":len(blob),"sheets":sheets,"source_parser":"incheon_education_xlsx"},None
    except Exception as exc:
        return [],{},f"{type(exc).__name__}: {str(exc)[:250]}"
