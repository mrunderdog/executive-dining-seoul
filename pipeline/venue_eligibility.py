"""Conservative non-venue filter for public dining disclosures.

A payment intermediary, chain-wide billing entity or confirmed florist/produce seller is not a mappable restaurant.
Do not apply fuzzy brand exclusions: individual physical branches must remain eligible.
"""
from __future__ import annotations

import re

NON_VENUE_EXACT = frozenset({
    "배달의민족",
    "우아한형제들",
    "스타벅스코리아",
    "네이버파이낸셜",
    "네이버페이",
    "카카오페이",
    "토스페이먼츠",
    "쿠팡이츠",
    "쿠팡",
    "네이버쇼핑",
    "11번가",
    "지마켓",
    "gmarket",
    "이마트몰",
    "화월청과",
    "우성화원",
})


def normalized_merchant(value: object) -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"^(?:주식회사|유한회사|\(주\)|㈜)\s*", "", raw)
    return re.sub(r"[^0-9a-z가-힣]", "", raw)


def is_non_venue_merchant(value: object) -> bool:
    """Only reject unambiguous intermediaries / generic billing entities."""
    key = normalized_merchant(value)
    return not key or key in NON_VENUE_EXACT
