#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/"reports"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152.0 Safari/537.36"

DATASETS={
    "gyeonggi_council_expense":{
        "infId":"K2ICW5AEWYG3KRUW4TO920297021",
        "infSeq":"1",
        "description":"의원 업무추진비 사용 현황",
    },
    "gyeonggi_daily_expense":{
        "infId":"LJ9Z18Z5KLJ1M32VO1BK27178834",
        "infSeq":"1",
        "description":"경기도 지출집행 현황(일상경비)",
    },
}


def probe(name,spec):
    url=(
        "https://data.gg.go.kr/portal/data/sheet/downloadSheetData.do"
        f"?downloadType=C&infId={spec['infId']}&infSeq={spec['infSeq']}"
    )
    req=urllib.request.Request(url,headers={
        "User-Agent":UA,
        "Accept":"text/csv,text/plain,*/*",
        "Accept-Language":"ko-KR,ko;q=0.9,en;q=0.5",
        "Referer":f"https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId={spec['infId']}&infSeq=1",
    })
    out={"key":name,"description":spec["description"],"url":url}
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            blob=r.read(65536)
            out.update({
                "status":r.status,
                "content_type":r.headers.get("Content-Type",""),
                "content_disposition":r.headers.get("Content-Disposition",""),
                "content_length":r.headers.get("Content-Length",""),
                "sample_bytes":len(blob),
            })
            txt=""; encoding=""
            for enc in ("utf-8-sig","cp949","euc-kr","utf-8"):
                try:
                    txt=blob.decode(enc); encoding=enc; break
                except UnicodeDecodeError:
                    pass
            lines=txt.splitlines() if txt else []
            out["encoding"]=encoding
            out["sample_lines"]=lines[:8]
            out["looks_csv"]=bool(lines and "," in lines[0])
    except Exception as e:
        out["error"]=f"{type(e).__name__}: {e}"
    return out


def main():
    rows=[probe(k,v) for k,v in DATASETS.items()]
    REPORTS.mkdir(exist_ok=True)
    payload={"generated_at":datetime.now().isoformat(timespec="seconds"),"datasets":rows}
    (REPORTS/"gyeonggi-open-data-probe.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    md=["# Gyeonggi Open Data direct-download probe",""]
    for r in rows:
        md += [
            f"## {r['description']}",
            "",
            f"- HTTP: {r.get('status','FAIL')}",
            f"- Content-Type: {r.get('content_type','')}",
            f"- Content-Disposition: {r.get('content_disposition','')}",
            f"- Content-Length: {r.get('content_length','')}",
            f"- Detected encoding: {r.get('encoding','')}",
            f"- Looks CSV: {r.get('looks_csv',False)}",
        ]
        if r.get("error"): md.append(f"- Error: {r['error']}")
        if r.get("sample_lines"):
            md += ["","Sample:"]
            md.extend("    "+x[:500] for x in r["sample_lines"])
        md.append("")
    (REPORTS/"gyeonggi-open-data-probe.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps(rows,ensure_ascii=False))
    if not any(r.get("status")==200 and r.get("looks_csv") for r in rows):
        raise SystemExit("No direct Gyeonggi CSV endpoint was usable")


if __name__=="__main__":
    main()
