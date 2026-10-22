#!/usr/bin/env python3
"""Read-only audit: official council ledger != verified point of card acceptance.

Uses only committed public council raw records and review metadata. Never
attributes an address from directories to a payment row. Output is operator
evidence for targeted existing-record requests; it is not an extra public page.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("icheon", "ansan", "hwaseong")
PRIORITIES = {
    "icheon": ("야반", "서경한우프라자", "성루"),
    "ansan": ("다인", "다빈", "양평해장국"),
    "hwaseong": ("훈장골", "훈장골갈비집", "뜰안에"),
}
MERCHANT_ID_FIELDS = ("merchant_id", "merchant_branch_id", "card_merchant_id",
                      "merchant_registration_number", "business_registration_number")
ADDRESS_FIELDS = ("address", "merchant_address", "card_merchant_address")
PROTECTED_FIELDS = ("card_number", "card_holder", "authorization_code")


def scan_source(source: str) -> dict:
    raw = json.loads((ROOT / "data" / "raw" / f"{source}_expense.json").read_text(encoding="utf-8"))
    review = json.loads((ROOT / "sources" / f"{source}_venue_review.json").read_text(encoding="utf-8"))
    candidates = json.loads((ROOT / "reports" / f"{source}-executive-candidates.json").read_text(encoding="utf-8"))
    rows = raw.get("rows", [])
    assert raw.get("source") == source and review.get("source") == source
    assert len(review.get("candidates", [])) == len(candidates.get("candidates", []))
    assert {x.get("merchant") for x in review["candidates"]} == {x.get("merchant") for x in candidates["candidates"]}
    # Never accept an asserted verified branch without an original transaction
    # trail. If an institution later supplies extra documents, verify first.
    if any(x.get("payment_branch_verified") for x in review["candidates"]):
        raise ValueError(f"{source}: asserted payment-branch verification needs independent source QA")
    address_rows = sum(any(str(x.get(k) or "").strip() for k in ADDRESS_FIELDS) for x in rows)
    merchant_id_rows = sum(any(str(x.get(k) or "").strip() for k in MERCHANT_ID_FIELDS) for x in rows)
    if any(any(k in x and x[k] for k in PROTECTED_FIELDS) for x in rows):
        raise ValueError(f"{source}: personal/payment credential field cannot be published")
    focus = []
    for name in PRIORITIES[source]:
        related = [x for x in rows if x.get("merchant") == name]
        if not related:
            raise ValueError(f"{source}: focus merchant absent: {name}")
        focus.append({
            "merchant": name,
            "matching_source_transactions": len(related),
            "payment_branch_status": "NOT_VERIFIED",
            "transactions": [
                {"row_id": x["row_id"], "date": x["used_date"],
                 "amount": x["amount"], "official_post_url": x["source_post_url"],
                 "official_attachment_url": x["source_attachment_url"]}
                for x in related
            ],
        })
    return {
        "source": source, "official_transactions": len(rows),
        "transactions_with_business_address": address_rows,
        "transactions_with_merchant_identifier": merchant_id_rows,
        "transactions_without_branch_evidence": len(rows) if not address_rows and not merchant_id_rows else None,
        "candidate_merchants": len(candidates["candidates"]),
        "reviewed_merchants": sum(x["review_status"] != "NOT_REVIEWED" for x in review["candidates"]),
        "source_files": len(raw.get("files") or []),
        "official_document_urls": sorted({x.get("source_post_url") for x in rows if x.get("source_post_url")}),
        "priority_merchants": focus,
    }


def build() -> dict:
    results = [scan_source(k) for k in SOURCES]
    return {
        "schema_version": 1,
        "scope": "official council transaction files available as of 2026-10-22",
        "methodology": "Check parsed original public-expense rows, not inferred geocodes or directory restaurant addresses.",
        "sources": results,
        "totals": {
            "transactions": sum(x["official_transactions"] for x in results),
            "with_merchant_address": sum(x["transactions_with_business_address"] for x in results),
            "with_merchant_identifier": sum(x["transactions_with_merchant_identifier"] for x in results),
            "candidate_merchants": sum(x["candidate_merchants"] for x in results),
            "reviewed_merchants": sum(x["reviewed_merchants"] for x in results),
            "priority_transactions": sum(sum(p["matching_source_transactions"] for p in x["priority_merchants"]) for x in results),
            "confirmed_payment_branches": 0,
        },
        "not_a_payment_branch_proof": ["same_name", "same_city", "business_directory", "map_geocode", "identical_brand"],
        "necessary_next_evidence": "An agency-held existing document linking each transaction to merchant branch address or a reproducible merchant identifier, redacted as required.",
        "public_policy": "No restaurant pin is to be described as the card-acceptance location unless independently verified at transaction level.",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=ROOT / "reports" / "council-payment-location-audit.json")
    p.add_argument("--check", action="store_true", help="Compare to committed audit snapshot")
    args = p.parse_args()
    payload = build()
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        existing = json.loads(args.output.read_text(encoding="utf-8"))
        if existing != payload:
            raise SystemExit("Council payment-branch evidence audit snapshot is stale or inconsistent")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(json.dumps(payload["totals"], ensure_ascii=False))


if __name__ == "__main__":
    main()
