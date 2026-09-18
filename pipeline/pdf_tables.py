from __future__ import annotations

import io


def pdf_tables(blob: bytes):
    """Yield (page-table label, rows) from text-based PDF tables.

    Uses pdfplumber's table detector. Image-only/scanned PDFs simply yield no
    tables and are therefore never published automatically.
    """
    import pdfplumber

    found = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables() or []
            for tno, table in enumerate(tables, 1):
                rows = []
                for row in table or []:
                    vals = [(" ".join(str(x or "").split()) if x is not None else "") for x in row]
                    if any(vals):
                        rows.append(vals)
                if rows:
                    found.append((f"page{pno}-table{tno}", rows))
    return found
