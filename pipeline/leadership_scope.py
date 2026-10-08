"""Leadership scope shared by education and police source adapters.

Only a published title / explicitly scoped official document may authorize a role.
Attendees and department names never imply that a leader made the payment.
"""
from __future__ import annotations
import re

def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())

NEGATIVE = re.compile(r"(?<![가-힣])(?:과장|팀장|담당자|주무관|사무관|교사|교직원|직원|계장|주임)(?![가-힣])")

EDUCATION_ROLES = (
    ("education_head", re.compile(r"(?<!부)교육감")),
    ("education_deputy", re.compile(r"(?:제[12])?부교육감")),
    ("education_branch_head", re.compile(r"(?:교육지원청장|교육장)")),
    ("director_general", re.compile(r"[가-힣0-9·]*?(?:실장|국장|본부장)")),
    ("director_general", re.compile(r"(?:정책기획조정관)")),
)
POLICE_ROLES = (
    ("police_head", re.compile(r"(?:경찰청장|경찰청 청장|시·도경찰청장|시도경찰청장)")),
    ("police_deputy", re.compile(r"(?:경찰청차장|경찰청 차장|경찰청장 직무대리)")),
    ("police_branch_head", re.compile(r"(?:경찰서장)")),
    ("police_bureau_head", re.compile(r"(?:국가수사본부장|[가-힣0-9·]*?(?:본부장|실장|국장|기획관)|대변인)")),
)

def classify_leadership_title(title: str, cohort: str) -> dict | None:
    """A conservative affirmative match from the *posting title* only."""
    s = clean(title)
    if "업무추진비" not in s:
        return None
    if "부서별" in s or "직원" in s or "과장" in s or "팀장" in s:
        return None
    patterns = EDUCATION_ROLES if cohort == "education_leadership" else (
        POLICE_ROLES if cohort == "police_leadership" else ()
    )
    # Test explicit deputies before heads, so 부교육감 never becomes 교육감.
    if cohort == "education_leadership":
        patterns = (EDUCATION_ROLES[1], EDUCATION_ROLES[0], *EDUCATION_ROLES[2:])
    for tier, pattern in patterns:
        match = pattern.search(s)
        if match:
            return {"tier": tier, "role": match.group(0), "role_source": "posting_title"}
    return None

def valid_transaction(row: dict, official_hosts: set[str]) -> bool:
    """Never publish inferred attendees, summaries or non-traceable transactions."""
    from datetime import date
    from urllib.parse import urlsplit
    role = clean(row.get("role"))
    try:
        day = date.fromisoformat(clean(row.get("used_date")))
        value = int(row.get("amount"))
        host = (urlsplit(clean(row.get("source_url"))).hostname or "").lower()
    except (TypeError, ValueError):
        return False
    if not (2000 <= day.year <= date.today().year and value > 0):
        return False
    merchant = clean(row.get("merchant"))
    if not merchant or merchant in {"-", "미상", "사용처", "장소", "비공개", "카드"}:
        return False
    if not any(host == allowed or host.endswith("." + allowed) for allowed in official_hosts):
        return False
    return bool(role) and clean(row.get("role_source")) in {"posting_title", "source_heading"}

