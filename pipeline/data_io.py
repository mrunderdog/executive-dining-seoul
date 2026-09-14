from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CHUNK_DIR = DATA_DIR / "chunks"
CANONICAL = DATA_DIR / "current.json.gz.b64"
CHUNK_SIZE = 17000


def _read_encoded() -> str:
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


def save_payload(payload: dict) -> None:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = base64.b64encode(gzip.compress(raw, compresslevel=9)).decode("ascii")
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    for old in CHUNK_DIR.glob("current.part*.b64"):
        old.unlink()
    for idx, start in enumerate(range(0, len(encoded), CHUNK_SIZE), start=1):
        (CHUNK_DIR / f"current.part{idx:02d}.b64").write_text(encoded[start:start+CHUNK_SIZE], encoding="ascii")
    if CANONICAL.exists():
        CANONICAL.unlink()


def write_plain_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
