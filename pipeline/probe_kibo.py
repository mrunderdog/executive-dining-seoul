#!/usr/bin/env python3
from __future__ import annotations
import io, subprocess
from pypdf import PdfReader

endpoint="https://www.kibo.or.kr/COMN0201/attchLocalFileDownload.do"
files=[
 ("기관장","JWATTCH-54-65231","9f65f3d8-2769-54de-2873-0ce42481ac00"),
 ("임원","JWATTCH-54-65232","96ca2c2e-9412-4e4f-fbd6-dbb09fa341fe"),
]
for role,file_id,file_key in files:
    out=f"/tmp/kibo-{role}.pdf"
    cmd=[
      "curl","-fSL","--retry","10","--retry-all-errors","--retry-delay","2",
      "--connect-timeout","6","--max-time","20",
      "-A","Mozilla/5.0",
      "-e","https://www.kibo.or.kr/main/board/boardType46.do?mode=list",
      "-d","attchFileDiv=file1",
      "-d",f"attchFileId={file_id}",
      "-d",f"attchFileKey={file_key}",
      endpoint,"-o",out
    ]
    print("CURL",role)
    subprocess.run(cmd,check=True)
    blob=open(out,"rb").read()
    print("DOWNLOAD",role,len(blob),blob[:8])
    pdf=PdfReader(io.BytesIO(blob))
    print("PAGES",role,len(pdf.pages))
    for i,p in enumerate(pdf.pages[:3],1):
        raw=p.extract_text() or ""
        print("RAW_LINES",role,i,repr(raw[:16000]))
        try:
            layout=p.extract_text(extraction_mode="layout") or ""
            print("LAYOUT",role,i,repr(layout[:16000]))
        except Exception as e:
            print("LAYOUT_ERR",role,i,type(e).__name__,e)
