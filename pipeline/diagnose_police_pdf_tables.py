#!/usr/bin/env python3
"""Print bounded structural diagnostics for Police Agency official PDF tables.

No inferred rows or publication. Each row/sample limited to avoid verbose logs.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pdfplumber

ROOT=Path(__file__).resolve().parents[1]
PDF_DIR=ROOT/"reports/police-browser-pdfs"
PROBE=ROOT/"reports/police-browser-attachment-probe.json"

def diagnose():
    if PROBE.exists():
        report=json.loads(PROBE.read_text(encoding="utf-8"))
        for record in report.get("records") or []:
            for attempt in record.get("attempts") or []:
                if attempt.get("parse_error"):
                    print("SOURCE_PARSE_ERROR",record["role"],attempt["parse_error"],flush=True)
    for pdf in sorted(PDF_DIR.glob("*.pdf"))[:12]:
        raw=pdf.read_bytes()
        if not raw.startswith(b"%PDF-"):continue
        print("PDF_LAYOUT",hashlib.sha256(raw).hexdigest()[:16],len(raw),flush=True)
        with pdfplumber.open(pdf) as obj:
            print("  PAGES",len(obj.pages),flush=True)
            for page in obj.pages[:2]:
                sample=(page.extract_text() or "").splitlines()[:14]
                print("  PAGE",page.page_number,"TEXT_LINES",len(sample),flush=True)
                for line in sample:
                    print("  TEXT",line[:170],flush=True)
                tables=page.extract_tables()
                print("  TABLES",len(tables),flush=True)
                for table in tables[:2]:
                    print("  SIZE",len(table),"COLS",max(map(len,table)) if table else 0,flush=True)
                    for cells in table[:8]:
                        print("  CELL",json.dumps([str(x or "")[:110] for x in cells[:12]],ensure_ascii=False),flush=True)
if __name__=="__main__":
    diagnose()
