"""Curated, provenance-bearing restaurant venue addresses; never payment evidence."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"sources/curated_venue_address_evidence.json"
APPROVED="APPROVED_VENUE_LOCATION"

def curated_location(cohort:str, merchant:str, registry:dict|None=None)->dict|None:
    """Resolve only an exact merchant name in an explicitly approved cohort.

    Official restaurant branch location is NOT bank/card merchant equivalence,
    historical presence, or an individual's attendance.
    """
    registry=registry if registry is not None else json.loads(REGISTRY.read_text(encoding="utf-8"))
    candidates=[v for v in registry["entries"] if v["cohort"]==cohort and v["merchant"]==merchant]
    if len(candidates)!=1:
        return None
    rec=candidates[0]
    if rec.get("status")!=APPROVED or not rec.get("address"):
        return None
    evidence=rec.get("evidence") or []
    if len(evidence)<2 or any(urlparse(x.get("url","")).scheme!="https" or not urlparse(x.get("url","")).hostname for x in evidence):
        return None
    hosts={urlparse(x["url"]).hostname.lower() for x in evidence}
    official=rec.get("basis")=="EXACT_NAMED_BRANCH_OFFICIAL_BRAND" and all(h in {"hiobaltan.com","www.hiobaltan.com"} for h in hosts)
    corroborated=rec.get("basis")=="EXACT_NAMED_BRANCH_CORROBORATED" and len(hosts)>=2
    if not (official or corroborated):
        return None
    return {
        "address":rec["address"],
        "basis":rec["basis"],
        "evidence_urls":[x["url"] for x in evidence],
        "venue_location_status":APPROVED,
        "payment_branch_verified":False,
        "individual_attendance_verified":False,
    }
