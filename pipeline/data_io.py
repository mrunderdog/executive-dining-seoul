from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CHUNK_DIR = DATA_DIR / "chunks"
CANONICAL = DATA_DIR / "current.json.gz.b64"

ORDERED_CHUNKS = [
    "current.part01a.b64",
    "current.part01b.b64",
    "current.part02.b64",
    "current.part03.b64",
    "current.part04.b64",
    "current.part05.b64",
]


def _read_encoded() -> str:
    explicit = [CHUNK_DIR / name for name in ORDERED_CHUNKS]
    if all(p.exists() for p in explicit):
        return "".join(p.read_text(encoding="ascii").strip() for p in explicit)

    parts = sorted(CHUNK_DIR.glob("current.part*.b64"))
    if parts:
        return "".join(p.read_text(encoding="ascii").strip() for p in parts)
    if CANONICAL.exists():
        return CANONICAL.read_text(encoding="ascii").strip()
    raise FileNotFoundError("canonical dataset not found under data/chunks or data/current.json.gz.b64")


def load_payload() -> dict:
    encoded = _read_encoded()
    raw = gzip.decompress(base64.b64decode(encoded))
    return json.loads(raw.decode("utf-8"))


def write_plain_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
