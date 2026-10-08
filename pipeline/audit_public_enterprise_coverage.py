#!/usr/bin/env python3
"""Read-only source coverage / contamination audit; never treats a registry flag as proof of publication."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from venue_eligibility import is_non_venue_merchant

ROOT = Path(__file__).resolve().parents[1]
def read(path):
    p = ROOT / path
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def audit():
    reg = read("sources/public_enterprise_registry.json").get("sources", [])
    raw = read("data/raw/public_enterprise_expense.json").get("rows", [])
    cands = read("reports/public-enterprise-candidates.json").get("candidates", [])
    raw_counts = Counter(str(r.get("institution") or "") for r in raw)
    candidate_counts = Counter(i for c in cands for i in c.get("institutions", []))
    rows = []
    for s in reg:
        inst = s["institution"]
        actual = raw_counts.get(inst, 0)
        candidates = candidate_counts.get(inst, 0)
        rows.append({
            "key": s["key"], "institution": inst,
            "publish_configured": bool(s.get("publish")),
            "refresh_policy": s.get("refresh_policy"),
            "raw_rows": actual, "candidate_entities": candidates,
            "diagnosis": (
                "TRACK_ONLY" if not s.get("publish") else
                "NO_RAW" if not actual else
                "NO_CANDIDATES" if not candidates else
                "HAS_CANDIDATES_NOT_PUBLISH_VERIFIED"
            ),
        })
    filtered = [c for c in cands if is_non_venue_merchant(c.get("merchant"))]
    return {
        "source_count": len(reg),
        "publish_configured_count": sum(bool(s.get("publish")) for s in reg),
        "tracked_count": sum(not s.get("publish") for s in reg),
        "raw_row_count": len(raw),
        "candidate_count": len(cands),
        "suspected_non_venues_in_existing_candidates": [
            {"merchant": c.get("merchant"), "institutions": c.get("institutions", [])}
            for c in filtered
        ],
        "sources": rows,
        "note": "Publication and geocoding are NOT verified by this pre-publication audit.",
    }

def main():
    result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert result["source_count"] > 0, "Missing source registry"

if __name__ == "__main__":
    main()
