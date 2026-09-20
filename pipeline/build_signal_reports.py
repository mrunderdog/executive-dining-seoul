#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from data_io import load_payload
from published_sources import merge_published_sources
from extra_published import merge_extra_published
from global_entities import canonical_address, merge_global_entities, strict_name

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def t(v) -> str:
    return " ".join(str(v or "").split()).strip()


def build_premerge_payload() -> dict:
    return merge_extra_published(
        merge_published_sources(load_payload())
    )


def build_payload() -> dict:
    return merge_global_entities(build_premerge_payload())


def build_cross_origin_review(pre_records: list[dict], merged_records: list[dict]) -> list[dict]:
    """Find exact-name cross-origin candidates that were intentionally not auto-merged."""
    merged_names = {
        strict_name(r.get("name"))
        for r in merged_records
        if int((r.get("cross_institution") or {}).get("source_count") or 0) >= 2
    }
    groups: dict[str, list[dict]] = {}
    for r in pre_records:
        name = strict_name(r.get("name"))
        if not name:
            continue
        groups.setdefault(name, []).append(r)

    out = []
    for name_key, rows in groups.items():
        origins = sorted({
            t(o)
            for r in rows
            for o in (r.get("origins") or ([r.get("origin")] if r.get("origin") else []))
            if t(o)
        })
        if len(origins) < 2 or name_key in merged_names:
            continue

        addressed = []
        address_keys = {}
        for r in rows:
            addr = t(r.get("address"))
            key = canonical_address(addr)
            if addr and key:
                addressed.append(r)
                address_keys.setdefault(key, set()).add(addr)

        if not addressed:
            continue

        institutions = sorted({
            t(i)
            for r in rows
            for i in (r.get("institutions") or ([r.get("institution")] if r.get("institution") else []))
            if t(i)
        })
        visits = sum(int((r.get("evidence") or {}).get("visits") or 0) for r in rows)
        qa_a = any(t(r.get("qa_grade")) == "A" for r in addressed)
        branch_named = any(
            strict_name(r.get("name")).endswith(("점", "지점", "호점"))
            for r in rows
        )
        unique_address = len(address_keys) == 1
        if unique_address and qa_a:
            confidence = "HIGH"
            reason = "exact name + single published address + QA A"
        elif unique_address and branch_named:
            confidence = "HIGH"
            reason = "explicit branch name + single published address"
        elif unique_address:
            confidence = "REVIEW"
            reason = "exact name + single published address"
        else:
            confidence = "AMBIGUOUS"
            reason = f"exact name but {len(address_keys)} addressed entities"

        display = t((rows[0].get("business") or {}).get("display") or rows[0].get("name"))
        out.append({
            "name": display,
            "strict_name": name_key,
            "confidence": confidence,
            "reason": reason,
            "origins": origins,
            "institutions": institutions,
            "visits": visits,
            "addresses": sorted({a for vals in address_keys.values() for a in vals}),
            "address_entity_count": len(address_keys),
            "qa_a": qa_a,
        })

    order = {"HIGH": 3, "REVIEW": 2, "AMBIGUOUS": 1}
    out.sort(
        key=lambda x: (order.get(x["confidence"], 0), len(x["origins"]), x["visits"]),
        reverse=True,
    )
    return out


def compact_record(r: dict) -> dict:
    e = r.get("evidence") or {}
    x = r.get("executive") or {}
    c = r.get("cross_institution") or {}
    return {
        "name": t((r.get("business") or {}).get("display") or r.get("name")),
        "address": t(r.get("address")),
        "origins": r.get("origins") or ([t(r.get("origin"))] if t(r.get("origin")) else []),
        "institutions": r.get("institutions") or ([t(r.get("institution"))] if t(r.get("institution")) else []),
        "cohorts": r.get("cohorts") or ([t(r.get("cohort"))] if t(r.get("cohort")) else []),
        "visits": int(e.get("visits") or 0),
        "spend": int(e.get("spend") or 0),
        "date_min": t(e.get("date_min")),
        "date_max": t(e.get("date_max")),
        "consensus_score": float(c.get("score") or 0),
        "institution_count": int(c.get("institution_count") or 0),
        "source_count": int(c.get("source_count") or 0),
        "top_role_tier": t(x.get("top_role_tier")),
        "top_role_label": t(x.get("top_role_label")),
        "top_official_visits": int(x.get("top_official_visits") or 0),
        "prime_minister_visits": int(x.get("prime_minister_visits") or 0),
        "deputy_prime_minister_visits": int(x.get("deputy_prime_minister_visits") or 0),
        "minister_visits": int(x.get("minister_visits") or 0),
        "vice_minister_visits": int(x.get("vice_minister_visits") or 0),
        "mayor_visits": int(x.get("mayor_visits") or 0),
        "vice_mayor_visits": int(x.get("vice_mayor_visits") or 0),
    }


def main():
    pre_payload = build_premerge_payload()
    pre_records = pre_payload.get("records") or []
    payload = merge_global_entities(pre_payload)
    records = payload.get("records") or []

    cross = [
        compact_record(r) for r in records
        if (r.get("cross_institution") or {}).get("is_cross")
    ]
    cross.sort(
        key=lambda x: (x["consensus_score"], x["institution_count"], x["visits"]),
        reverse=True,
    )

    top_official = [
        compact_record(r) for r in records
        if int((r.get("executive") or {}).get("top_official_visits") or 0) > 0
    ]
    top_official.sort(
        key=lambda x: (x["top_official_visits"], x["visits"], x["date_max"]),
        reverse=True,
    )

    regional_heads = [
        compact_record(r) for r in records
        if (
            int((r.get("executive") or {}).get("mayor_visits") or 0)
            + int((r.get("executive") or {}).get("vice_mayor_visits") or 0)
        ) > 0
    ]
    regional_heads.sort(
        key=lambda x: (x["mayor_visits"] + x["vice_mayor_visits"], x["visits"]),
        reverse=True,
    )

    cross_origin_review = build_cross_origin_review(pre_records, records)

    stats = payload.get("stats") or {}
    doc = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_records": len(records),
        "cross_institution_count": len(cross),
        "cross_origin_count": sum(1 for x in cross if x["source_count"] >= 2),
        "top_official_count": len(top_official),
        "regional_head_count": len(regional_heads),
        "entity_merges": int(stats.get("entity_merges") or 0),
        "cross_origin_review_count": len(cross_origin_review),
        "cross_origin_review": cross_origin_review,
        "cross_institution": cross,
        "top_official": top_official,
        "regional_heads": regional_heads,
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "signal-intelligence.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md = [
        "# Executive Dining signal intelligence",
        "",
        f"- Generated: {doc['generated_at']}",
        f"- Published restaurant entities: **{len(records)}**",
        f"- Cross-institution restaurants: **{len(cross)}**",
        f"- Cross-origin restaurants: **{doc['cross_origin_count']}**",
        f"- Central top-official restaurants: **{len(top_official)}**",
        f"- Regional mayor/vice-mayor restaurants: **{len(regional_heads)}**",
        f"- Entity merges: **{doc['entity_merges']}**",
        f"- Cross-origin review candidates: **{len(cross_origin_review)}**",
        "",
        "> This report ranks restaurant-selection signals, not public officials or political actors.",
        "",
        "## Cross-institution consensus",
        "",
        "| # | Restaurant | Consensus | Institutions | Sources | Visits | Origins |",
        "|---:|---|---:|---:|---:|---:|---|",
    ]
    for i, x in enumerate(cross[:100], 1):
        origins = " · ".join(x["origins"])
        md.append(
            f"| {i} | {x['name'].replace('|','/')} | {x['consensus_score']:.1f} | "
            f"{x['institution_count']} | {x['source_count']} | {x['visits']} | {origins.replace('|','/')} |"
        )

    md += [
        "",
        "## Cross-origin review queue",
        "",
        "| # | Restaurant | Confidence | Origins | Visits | Address entities | Reason |",
        "|---:|---|---|---|---:|---:|---|",
    ]
    for i, x in enumerate(cross_origin_review[:100], 1):
        md.append(
            f"| {i} | {x['name'].replace('|','/')} | {x['confidence']} | "
            f"{' · '.join(x['origins']).replace('|','/')} | {x['visits']} | "
            f"{x['address_entity_count']} | {x['reason'].replace('|','/')} |"
        )

    md += [
        "",
        "## Central top-official dining signal",
        "",
        "| # | Restaurant | Highest role | Top-official visits | Minister | Vice minister | Institutions | Visits |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for i, x in enumerate(top_official[:100], 1):
        md.append(
            f"| {i} | {x['name'].replace('|','/')} | {x['top_role_label'] or '-'} | "
            f"{x['top_official_visits']} | {x['minister_visits']} | {x['vice_minister_visits']} | "
            f"{len(x['institutions'])} | {x['visits']} |"
        )

    md += [
        "",
        "## Regional executive dining signal",
        "",
        "| # | Restaurant | Mayor | Vice mayor | Visits | Origin |",
        "|---:|---|---:|---:|---:|---|",
    ]
    for i, x in enumerate(regional_heads[:100], 1):
        md.append(
            f"| {i} | {x['name'].replace('|','/')} | {x['mayor_visits']} | "
            f"{x['vice_mayor_visits']} | {x['visits']} | {' · '.join(x['origins']).replace('|','/')} |"
        )

    (REPORTS / "signal-intelligence.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({
        "records": len(records),
        "cross_institution": len(cross),
        "cross_origin": doc["cross_origin_count"],
        "top_official": len(top_official),
        "regional_heads": len(regional_heads),
        "entity_merges": doc["entity_merges"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
