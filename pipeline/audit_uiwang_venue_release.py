#!/usr/bin/env python3
"""Fail-closed Uiwang 7–10/2026 restaurant-identity and ranking preflight.

Uses integrated, source-verified candidates. DOES NOT write to data/raw,
scores, published source files, or the website. Name-only similarity never
establishes that two card payees are the same physical restaurant.
"""
from __future__ import annotations
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from build_source_candidates import (
    looks_meal, plausible_transaction, role_bucket, normalize_merchant_name,
)
from published_sources import SOURCE_SPECS

ROOT = Path(__file__).resolve().parents[1]
SPEC = SOURCE_SPECS["uiwang"]
DINING_REVIEW_ONLY = (
    "커피", "카페", "파리바게", "투썸", "스타벅스", "이디야",
    "컴포즈", "메가엠지씨", "빵", "베이커리", "과일공작소",
)
UNCERTAIN_PAYEE = {"스타", "194*F"}
LEGAL_PREFIX = re.compile(r"^(?:주식회사|\(주\)|㈜)\s*")


def date_verified(row):
    period = row.get("source_period")
    try:
        value = date.fromisoformat(str(row.get("used_date") or ""))
        return (isinstance(period, list) and len(period) == 3
                and [value.year, value.month] == period[:2])
    except (ValueError, TypeError):
        return False


def observed_time(row):
    """Only dates in official source fields can support evening spend."""
    provided = str(row.get("used_time") or "").strip()
    if not provided:
        return ""
    found = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", provided)
    return f"{int(found.group(1)):02d}:{found.group(2)}" if found else ""


def suspected_alias_groups(rows):
    """Suggestions for human comparison; never merge amounts or visit counts."""
    families = defaultdict(set)
    for row in rows:
        name = normalize_merchant_name(row.get("merchant"))
        family = re.sub(r"[^0-9a-z가-힣]", "", LEGAL_PREFIX.sub("", name).lower())
        if family:
            families[family].add(name)
    return [{"potential_family": family, "source_names": sorted(names),
             "resolution": "UNVERIFIED_DO_NOT_MERGE"}
            for family, names in sorted(families.items())
            if len(names) > 1]


def assess_venues(rows):
    """Distinguish source validity, dining eligibility and issuer-ranking threshold.

    This is intentionally NOT a definitive restaurant identity verification.
    """
    failures = []
    if len(rows) != 193 or len({x.get("row_id") for x in rows}) != len(rows):
        failures.append("integrated_candidate_coverage_or_duplicate_id")
    grouped = defaultdict(list)
    decisions = []
    for row in rows:
        name = normalize_merchant_name(row.get("merchant"))
        date_ok = date_verified(row)
        role = role_bucket(row.get("role"), include_committees=False)
        is_meal = looks_meal(row) and plausible_transaction(row)
        reason = []
        if not date_ok:
            reason.append("UNVERIFIED_SOURCE_PERIOD")
            failures.append("candidate_official_period_mismatch")
        if not is_meal:
            reason.append("EXISTING_DINING_RULE_EXCLUDES")
        if any(term in name for term in DINING_REVIEW_ONLY):
            reason.append("COFFEE_BAKERY_OR_RETAIL_REVIEW")
        if name in UNCERTAIN_PAYEE:
            reason.append("AMBIGUOUS_MERCHANT_IDENTITY")
        if not role:
            reason.append("NO_VERIFIED_CHAIR_VICECHAIR_ROLE")
        if not row.get("address"):
            reason.append("NO_CONFIRMED_PAYMENT_BRANCH_ADDRESS")
        if not observed_time(row):
            reason.append("NO_CONFIRMED_TIME")
        # Exact merchant label only; no speculation about a legal name,
        # physical branch, or equivalence between distinct original names.
        if (date_ok and is_meal
                and not any(term in name for term in DINING_REVIEW_ONLY)
                and name not in UNCERTAIN_PAYEE
                and role):
            grouped[name].append(row)
        decisions.append({"row_id": row.get("row_id"),
                          "merchant": name,
                          "source_date": row.get("used_date"),
                          "amount_krw": row.get("amount"),
                          "role": role or "",
                          "source_row": row.get("source_row"),
                          "source_sheet": row.get("source_sheet"),
                          "score_eligible": date_ok and is_meal
                          and not any(term in name for term in DINING_REVIEW_ONLY)
                          and name not in UNCERTAIN_PAYEE and bool(role),
                          "review_reasons": reason})
    preview = []
    for name, group in grouped.items():
        visits = len(group)
        months = len({r["used_date"][:7] for r in group})
        roles = len({role_bucket(r.get("role")) for r in group})
        spend = sum(int(r.get("amount") or 0) for r in group)
        evening = sum(int(observed_time(r).split(":")[0]) >= 17
                      for r in group if observed_time(r))
        score = min(100, round(
            35 * min(visits / 10, 1)
            + 25 * min(months / 5, 1)
            + 20 * min(roles / 2, 1)
            + 10 * (evening / visits if visits else 0)
            + 10 * min(spend / 3_000_000, 1), 1))
        qualifies = (visits >= SPEC["min_visits"]
                     and months >= SPEC["min_months"]
                     and score >= SPEC["min_score"])
        preview.append({
            "merchant": name, "score": score,
            "visits": visits, "months": months, "roles": roles,
            "evening": evening, "spend": spend,
            "passes_existing_threshold": qualifies,
            "payment_branch_identity": "NOT_VERIFIED",
            "publication_status": "HOLD_ENTITY_REVIEW",
        })
    preview.sort(key=lambda x: (-x["score"], -x["visits"], x["merchant"]))
    result = {
        "audit_scope": "uiwang 2026-07 to 2026-10 new rows only",
        "source_rows": len(rows),
        "unique_source_merchant_labels": len({x.get("merchant") for x in rows}),
        "unverified_role_rows": sum(not d["role"] for d in decisions),
        "rows_with_no_verified_time": sum(not observed_time(r) for r in rows),
        "rows_with_no_verified_address": sum(not r.get("address") for r in rows),
        "preliminary_score_input_rows": sum(d["score_eligible"] for d in decisions),
        "preliminary_merchants": len(preview),
        "threshold_pass_merchants": sum(x["passes_existing_threshold"] for x in preview),
        "identity_verified_merchants": 0,
        "source_validation": "PASS" if not failures else "HOLD",
        "release_decision": "HOLD_IDENTITY_AND_RANKING",
        "failures": sorted(set(failures)),
        "publish": False,
        "policy": "No automatic alias merge, card-branch inference, new restaurant entity, or rank publication.",
    }
    return result, decisions, preview, suspected_alias_groups(rows)


def main():
    inp = ROOT / "reports/recovery/uiwang-integrated/recommendation_candidates.json"
    rows = json.loads(inp.read_text(encoding="utf-8"))
    result, decisions, preview, aliases = assess_venues(rows)
    out = ROOT / "reports/recovery/uiwang-venue"
    out.mkdir(parents=True, exist_ok=True)
    for filename, value in (
        ("audit.json", result),
        ("transaction_screening.json", decisions),
        ("merchant_score_preview.json", preview),
        ("alias_review_only.json", aliases),
    ):
        (out / filename).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if result["source_validation"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
