#!/usr/bin/env python3
"""Determine exact type and contents of 1328 'compressed download' (read-only).

An archive is not necessarily XLSX just because it starts with PK. Inspect
members, enforce paths/size limits and compare against the already downloaded
three Q3 leadership spreadsheets before accepting any unique transactions.
"""
import hashlib
import io
import json
import zipfile
from pathlib import Path
from ingest_council_expense import fetch_binary

ROOT=Path(__file__).resolve().parents[1]
URL="https://www.icouncil.go.kr/main/bbs/bbsMsgFileDownCompress.do?bcd=infordisc&msg_seq=1328"
REF="https://www.icouncil.go.kr/main/bbs/bbsMsgDetail.do?bcd=infordisc&msg_seq=1328"
def inspect(blob):
    out={"url":URL,"sha256":hashlib.sha256(blob).hexdigest(),
         "bytes":len(blob),"magic":blob[:16].hex(),"members":[],
         "status":"HOLD","publish":False}
    if not blob.startswith(b"PK") or not zipfile.is_zipfile(io.BytesIO(blob)):
        out["reason"]="not_a_recognized_zip_archive"
        return out
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names=set(z.namelist())
        if "[Content_Types].xml" in names:
            out["reason"]="OOXML_workbook_not_compressed_archive"
            return out
        members=z.infolist()
        if len(members)>80 or sum(x.file_size for x in members)>50_000_000:
            out["reason"]="archive_member_limits_exceeded"
            return out
        for item in members:
            name=item.filename
            # Windows-generated ZIPs legitimately use backslashes as path
            # separators. Inspect read-only, normalize only for validation.
            normalized=name.replace("\\","/")
            unsafe=(normalized.startswith("/") or
                    normalized.startswith("//") or
                    ".." in Path(normalized).parts or
                    (len(normalized)>1 and normalized[1]==":") or
                    bool(item.flag_bits & 1))
            if unsafe:
                out["members"].append({"name":name,"reason":"unsafe_archive_member"})
                out["reason"]="unsafe_archive_member"
                return out
            if item.is_dir():
                continue
            info={"name":name,"size":item.file_size,
                  "supported":name.lower().endswith((".xlsx",".xls",".csv",".pdf"))}
            if info["supported"]:
                payload=z.read(item)
                info["sha256"]=hashlib.sha256(payload).hexdigest()
            out["members"].append(info)
        out["reason"]="archive_inventory_requires_comparison_to_existing_official_Q3_files"
        out["supported_files"]=sum(x["supported"] for x in out["members"])
    return out

def main():
    try:
        blob=fetch_binary(URL,REF)
        result=inspect(blob)
    except Exception as exc:
        result={"url":URL,"status":"HOLD","publish":False,
                "reason":"official_download_failed","error_type":type(exc).__name__}
    out=ROOT/"reports/recovery/incheon-archive"
    out.mkdir(parents=True,exist_ok=True)
    (out/"manifest.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
