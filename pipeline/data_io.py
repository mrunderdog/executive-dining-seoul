from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "current.json.gz.b64"


def load_payload() -> dict:
    raw = gzip.decompress(base64.b64decode(CANONICAL.read_text(encoding="ascii")))
    return json.loads(raw.decode("utf-8"))


def save_payload(payload: dict) -> None:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    CANONICAL.write_text(base64.b64encode(gzip.compress(raw, compresslevel=9)).decode("ascii"), encoding="ascii")


def write_plain_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
