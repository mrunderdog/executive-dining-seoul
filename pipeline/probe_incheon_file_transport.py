#!/usr/bin/env python3
"""One-shot read-only HTTPS transport probe for actual Incheon list hrefs.

Do NOT use a successful transport probe as row verification/publication.
Only exact URLs seen in official HTML listing and exact expected SHA for
previously captured PDF file are evaluated. No certificate bypass.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

OBSERVED = {
  1326: ("https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&msg_seq=1326&fileno=1",
         "e1459b54a55c040caa86af3f5fcc582a630543b79cf6030acc86f96153a97e1e"),
  1327: ("https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&msg_seq=1327&fileno=1",
         "44129be489aee23846fa19c4e0de465ef105164be42f74e2a1fe99c06d5b89dd"),
  1333: ("https://www.icouncil.go.kr/main/bbs/bbsMsgFileDown.do?bcd=infordisc&msg_seq=1333&fileno=1",
         None),
}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--seq",type=int,choices=sorted(OBSERVED),required=True)
    a=p.parse_args()
    url,sha=OBSERVED[a.seq]
    path=Path(f"reports/recovery/incheon-transport-{a.seq}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd=["curl","--fail","--silent","--show-error",
         "--connect-timeout","6","--max-time","18",
         "--max-filesize","30000000","--proto","=https",
         "--http1.1","--user-agent",
         "ExecutiveDiningSeoul/1.1 (+https://github.com/mrunderdog/executive-dining-seoul)",
         url]
    result={"seq":a.seq,"url":url,"prior_official_sha256":sha,
            "publication_authorized":False,"transport":"curl_verified_https"}
    try:
        p=subprocess.run(cmd,capture_output=True,timeout=20,check=False)
        result["exit_code"]=p.returncode
        result["error"]=p.stderr.decode("utf-8",errors="replace")[-500:]
        blob=p.stdout
        result["bytes"]=len(blob)
        result["sha256"]=hashlib.sha256(blob).hexdigest() if blob else None
        result["pdf_magic"]=blob.startswith(b"%PDF")
        result["zip_magic"]=blob.startswith(b"PK")
        result["status"]=(
            "VERIFIED_SOURCE_BYTES" if p.returncode==0 and sha and
                result["sha256"]==sha and result["pdf_magic"]
            else "UNPINNED_SOURCE_BYTES" if p.returncode==0 and not sha and
                (result["pdf_magic"] or result["zip_magic"])
            else "HOLD"
        )
    except Exception as e:
        result.update(status="HOLD",error=f"{type(e).__name__}: {e}")
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    if result["status"]=="HOLD":
        raise SystemExit(2)

if __name__=="__main__":
    main()
