#!/usr/bin/env python3
"""Source-pinned scanned Yongin PDF OCR review; never writes transaction data.

A scan is not a verified row. This tool creates page images and bounded OCR
evidence for manual official-source reconciliation. The strict publication gate
remains HOLD until independent row/date/amount/merchant checks are complete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

YONGIN_2026_09_SHA256 = "a43ce6736e8d42cc086c31ecaf935ce5146e550229b25e311e48580d83abe01c"
MAX_PAGES = 6

# Human visual review of all six original page images (PDF SHA pinned above).
# These are document control totals, NOT approval to publish OCR rows.
PAGE_CONTROL_AMOUNTS = (
    (41580, 126000),
    (350700, 72000, 239000, 326000, 99000, 300000, 100000),
    (353000, 391000, 289600, 40000, 226000, 88000, 283000, 66000, 196000),
    (311000, 350000, 200000, 43000),
    (68000, 354000, 125500, 96000, 115900, 365500),
    (110500, 29200, 76000, 215000, 77320, 30000, 34300, 26000,
     14040, 71500, 300000, 29600, 32000, 13500, 158000, 122000),
)
PAGE_ROLES = (
    "의사입법담당관", "의회운영위원장", "자치행정위원장",
    "문화복지위원장", "경제환경위원장", "도시건설위원장",
)
# Page 2's source '사용처' column sometimes repeats the purpose of the
# meeting, rather than naming a merchant. Do not fabricate merchant names.
PAGE_2_VENUE_UNRESOLVED_ROWS = (1, 2, 3, 4, 5, 6)


def verified_page_controls():
    controls = [
        {"page": i + 1, "role": PAGE_ROLES[i],
         "source_rows": len(amounts),
         "source_amount_krw": sum(amounts)}
        for i, amounts in enumerate(PAGE_CONTROL_AMOUNTS)
    ]
    return {
        "pages": controls,
        "expected_official_rows": sum(c["source_rows"] for c in controls),
        "expected_official_amount_krw": sum(c["source_amount_krw"] for c in controls),
        "unidentified_venue": {
            "page": 2, "source_row_numbers": list(PAGE_2_VENUE_UNRESOLVED_ROWS),
            "meaning": "source merchant field describes staff meals, not a verified venue",
            "disposition": "HOLD; do not turn purpose text into restaurant name",
        },
        "source": "manual page-image review of SHA-256 pinned official PDF",
        "publication_status": "NOT_APPROVED",
    }


def verify_original(blob: bytes, expected_sha: str = YONGIN_2026_09_SHA256) -> str:
    digest = hashlib.sha256(blob).hexdigest()
    if digest != expected_sha:
        raise ValueError("official_pdf_sha256_mismatch: do not OCR or publish changed source")
    if not blob.startswith(b"%PDF"):
        raise ValueError("verified_source_not_pdf")
    return digest


def build_review(pdf: Path, outdir: Path) -> dict:
    # Dependencies are kept out of the production ingest pipeline.
    import fitz
    from PIL import Image
    import pytesseract

    blob = pdf.read_bytes()
    digest = verify_original(blob)
    document = fitz.open(stream=blob, filetype="pdf")
    if len(document) != MAX_PAGES:
        raise ValueError("official_pdf_page_count_changed: requires new source verification")

    outdir.mkdir(parents=True, exist_ok=True)
    page_reports = []
    for page_index, page in enumerate(document, 1):
        # Render from the SHA-locked original, not a synthetic rebuilt PDF.
        image = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False)
        png = outdir / f"yongin-2026-09-page-{page_index:02d}.png"
        image.save(png)
        pil = Image.frombytes("RGB", (image.width, image.height), image.samples)
        data = pytesseract.image_to_data(
            pil, lang="kor+eng", config="--psm 6",
            output_type=pytesseract.Output.DICT,
        )
        lines = defaultdict(list)
        for idx, value in enumerate(data.get("text", [])):
            word = (value or "").strip()
            if not word:
                continue
            conf = float(data["conf"][idx])
            key = (int(data["block_num"][idx]), int(data["par_num"][idx]),
                   int(data["line_num"][idx]))
            lines[key].append({
                "text": word, "confidence": conf,
                "bbox_px": [int(data[k][idx]) for k in ("left", "top", "width", "height")],
            })
        line_evidence = []
        for key, words in sorted(lines.items()):
            line_evidence.append({
                "line_key": list(key),
                "provisional_text": " ".join(x["text"] for x in words),
                "min_word_confidence": min(x["confidence"] for x in words),
                "words": words,
            })
        page_reports.append({
            "source_page": page_index, "image": png.name,
            "png_sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
            "pixel_size": [image.width, image.height],
            "ocr_lines": line_evidence,
        })

    report = {
        "source": "yongin",
        "period": "2026-09",
        "source_pdf_sha256": digest,
        "pages": page_reports,
        "source_control_totals": verified_page_controls(),
        "status": "MANUAL_OFFICIAL_ROW_RECONCILIATION_REQUIRED",
        "publication": "FORBIDDEN_FROM_OCR_ALONE",
        "required_checks": ["each original date", "each original merchant",
                            "each original amount", "source row counts and totals",
                            "no duplicated or omitted rows", "strict QA unchanged"],
    }
    dest = outdir / "yongin-2026-09-ocr-review.json"
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "pages": len(page_reports),
        "ocr_lines": sum(len(x["ocr_lines"]) for x in page_reports),
        "review_path": str(dest),
    }, ensure_ascii=False))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    build_review(args.pdf, args.outdir)


if __name__ == "__main__":
    main()
