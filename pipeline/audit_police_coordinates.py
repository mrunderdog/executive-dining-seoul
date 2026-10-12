#!/usr/bin/env python3
"""Fail closed when approved Police expense venues cannot be mapped accurately."""
from __future__ import annotations
import json
from coordinate_selection import select_coordinate
from geocode_cache import CACHE, fingerprint, GEOCODER_VERSION, POLICY_VERSION
from police_expense_publication import load_police_expense_records

def audit():
    cache=json.loads(CACHE.read_text(encoding="utf-8")).get("records",{})
    records=load_police_expense_records()
    problems=[]
    for record in records:
        key=f"{record['name']}|{record['origin']}"
        row=cache.get(key) or {}
        if row.get("fingerprint")!=fingerprint(record) or row.get("geocoder_version")!=GEOCODER_VERSION or row.get("policy_version")!=POLICY_VERSION:
            problems.append(f"{key}:missing_or_stale_cache")
            continue
        selected,coords,_=select_coordinate(record,cache)
        if selected!=key or not coords or not (37.0<=coords["lat"]<=38.0 and 126.5<=coords["lon"]<=127.5):
            problems.append(f"{key}:address_coordinate_mismatch")
    print(json.dumps({"approved_police_venues":len(records),"errors":problems},ensure_ascii=False))
    if problems:raise SystemExit(1)

if __name__=="__main__":
    audit()
