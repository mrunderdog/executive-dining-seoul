"""Senior-official publication scope for education and police expenditure data.

The actor of a transaction is the official named by the *publication/attachment*,
not anyone who merely attended the meal. Unknown/mixed titles remain unpublished.
"""
from __future__ import annotations
import re

ROLES = {
    "education_leadership": (
        ("제1부교육감", "부교육감"), ("제2부교육감", "부교육감"),
        ("부교육감", "부교육감"), ("교육감", "교육감"),
        ("기획조정실장", "실장"), ("실장", "실장"),
        ("국장", "국장"), ("본부장", "본부장"),
    ),
    "police_leadership": (
        ("국가수사본부장", "본부장"), ("경찰청차장", "차장"),
        ("경찰청 차장", "차장"), ("경찰청장", "청장"),
        ("수사기획조정관", "조정관"),
        ("국장", "국장"), ("실장", "실장"),
        ("본부장", "본부장"), ("감사관", "감사관"),
    ),
}

# Some publications say "2025년 XX국 업무추진비" but do not name
# the executive: an institutional unit is not itself an identified role.
REJECT_PHRASES = ("과장", "팀장", "담당자", "주무관", "사무관", "지원관")


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def role_from_title(title: object, cohort: str) -> str:
    name = clean(title)
    # Scope must appear in the ownership/title, not in a generic institution
    # name ("경기도교육청" doesn't identify the spending official).
    if not name or any(x in name for x in REJECT_PHRASES):
        return ""
    candidates = ROLES.get(cohort, ())
    for token, role in candidates:
        if token in name:
            return role
    return ""


def senior_role_eligible(title: object, cohort: str) -> bool:
    return bool(role_from_title(title, cohort))


def normalize_date(value: object) -> str:
    s = clean(value)
    m = re.search(r"(20\d{2})[-./년\s]+(\d{1,2})[-./월\s]+(\d{1,2})", s)
    if not m:
        return ""
    try:
        from datetime import date
        return date(*map(int, m.groups())).isoformat()
    except ValueError:
        return ""


def publishable_transaction(row: dict) -> bool:
    """Conservative exact evidence gate; not a substitute for venue QA."""
    from venue_eligibility import is_non_venue_merchant
    return (
        row.get("cohort") in ROLES
        and bool(role_from_title(row.get("source_role_title"), row["cohort"]))
        and bool(normalize_date(row.get("used_date")))
        and isinstance(row.get("amount"), int)
        and row["amount"] > 0
        and bool(clean(row.get("merchant")))
        and not is_non_venue_merchant(row.get("merchant"))
        and str(row.get("source_url") or "").startswith("https://")
        and row.get("source_document_verified") is True
    )
