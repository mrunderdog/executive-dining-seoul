#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime
from pathlib import Path

from ingest_central_executive_expense import clean, normalize, rows_from

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/"reports"
RAW_DIR=ROOT/"data"/"raw"
DISCOVERY=REPORTS/"incheon-executive-discovery.json"
UA="ExecutiveDiningSeoul/2.2 (+https://github.com/mrunderdog/executive-dining-seoul)"


def fetch_binary(url: str) -> bytes:
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"*/*"})
    with urllib.request.urlopen(req,timeout=15) as r:
        return r.read()


def main():
    if not DISCOVERY.exists():
        raise SystemExit(f"missing discovery report: {DISCOVERY}")
    d=json.loads(DISCOVERY.read_text(encoding="utf-8"))
    posts=d.get("posts") or []
    if not posts:
        raise SystemExit("no Incheon executive posts to ingest")

    all_rows=[]; files=[]; errors=[]
    for post in posts:
        for att in post.get("attachments") or []:
            url=att.get("url") or ""
            if not url: continue
            label=clean(att.get("text")) or url
            try:
                blob=fetch_binary(url)
                info={
                    "title":post.get("title"),
                    "scope":post.get("scope"),
                    "role":post.get("role"),
                    "url":url,
                    "name":label,
                    "bytes":len(blob),
                    "sha256":hashlib.sha256(blob).hexdigest(),
                    "sheets":[],
                }
                for sheet,rows in rows_from(blob,label):
                    norm,si=normalize(rows,sheet,{
                        "key":"incheon_metropolitan_government",
                        "institution":"인천광역시청",
                        "url":url,
                        "default_role":post.get("role") or "",
                    })
                    for r in norm:
                        r["region"]="인천"
                        r["jurisdiction"]="인천광역시"
                        r["cohort"]="regional_executive"
                        r["source_post_url"]=post.get("post_url") or ""
                        r["source_period"]=post.get("period")
                        r["scope"]=post.get("scope") or ""
                        if not clean(r.get("role")):
                            r["role"]=post.get("role") or ""
                        if not clean(r.get("department")) and post.get("scope")=="headquarters":
                            r["department"]="본청 실국과장 공개분"
                        r["row_id"]=hashlib.sha256(
                            "|".join(str(r.get(k,"")) for k in (
                                "institution","role","department","used_date","merchant","amount",
                                "source_url","source_sheet","source_row"
                            )).encode("utf-8")
                        ).hexdigest()[:20]
                    info["sheets"].append(si)
                    all_rows.extend(norm)
                files.append(info)
            except Exception as e:
                errors.append({"post":post.get("title"),"url":url,"error":f"{type(e).__name__}: {e}"})

    unique={r["row_id"]:r for r in all_rows}
    rows=sorted(unique.values(),key=lambda r:(r.get("used_date") or "",r.get("role") or "",r["row_id"]))
    if not rows:
        raise SystemExit(f"Incheon executive ingestion produced no rows; files={len(files)} errors={len(errors)}")

    RAW_DIR.mkdir(exist_ok=True)
    payload={
        "schema_version":1,
        "source":"incheon_province",
        "generated_at":datetime.now().isoformat(timespec="seconds"),
        "row_count":len(rows),
        "rows":rows,
        "files":files,
        "errors":errors,
    }
    out=RAW_DIR/"incheon_province_expense.json"
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

    md=[
        "# Incheon Metropolitan Government expense ingestion","",
        f"- Normalized rows: **{len(rows)}**",
        f"- Files: **{len(files)}**",
        f"- Errors: **{len(errors)}**","",
        "## Files","",
    ]
    for f in files:
        md.append(f"- {f.get('role') or f.get('scope') or '-'} — `{f.get('name','')[:100]}` — {sum(s.get('parsed_rows',0) for s in f.get('sheets',[]))} rows")
    if errors:
        md += ["","## Errors",""]
        md.extend(f"- {e}" for e in errors)
    (REPORTS/"incheon-province-ingestion.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"rows":len(rows),"files":len(files),"errors":len(errors)},ensure_ascii=False))


if __name__=="__main__":
    main()
