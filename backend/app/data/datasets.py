"""Registry of selectable datasets: the preloaded ones shipped with the app plus
any uploaded at runtime. Selecting one swaps the active dataset in the loader.
"""
from __future__ import annotations

from pathlib import Path

from app.config import REPO_ROOT
from app.data import loader

UPLOAD_DIR = REPO_ROOT / "data" / "uploads"

# Preloaded datasets. `answer_key` is optional (used only by the benchmark).
_PRELOADED: list[dict] = [
    {
        "id": "track02",
        "name": "Track 02 — Crestline Bank",
        "description": "90 days · ~300 accounts · the official Fraud Watch challenge.",
        "path": str(REPO_ROOT / "data" / "track02_fraud_watch.csv"),
        "answer_key": {
            "ring": [
                "AC-0001", "AC-0002", "AC-0003", "AC-0005", "AC-0006",
                "AC-0007", "AC-0009", "AC-0010", "AC-0011", "AC-0012",
            ],
            "exposure": 161750.90,
        },
    },
    {
        "id": "ring_b",
        "name": "Synthetic — Ring B",
        "description": "A different planted ring: 7 accounts, ~$4.8k structuring, late-night.",
        "path": str(REPO_ROOT / "data" / "synthetic_ring_b.csv"),
        "answer_key": {
            "ring": [
                "AC-0500", "AC-0501", "AC-0502", "AC-0503",
                "AC-0504", "AC-0505", "AC-0506",
            ],
        },
    },
    {
        "id": "ring_c",
        "name": "Synthetic — Ring C",
        "description": "11 accounts · ~$3k structuring · midday burst · fan-in collection hub.",
        "path": str(REPO_ROOT / "data" / "test-rings" / "ring_c_fanin.csv"),
        "answer_key": {
            "ring": [
                "AC-0600", "AC-0601", "AC-0602", "AC-0603", "AC-0604", "AC-0605",
                "AC-0606", "AC-0607", "AC-0608", "AC-0609", "AC-0610",
            ],
            "exposure": 846252.35,
        },
    },
    {
        "id": "ring_d",
        "name": "Synthetic — Ring D",
        "description": "9 accounts · ~$10k structuring · weekend/night · 4-hop layering chain.",
        "path": str(REPO_ROOT / "data" / "test-rings" / "ring_d_chain.csv"),
        "answer_key": {
            "ring": [
                "AC-0700", "AC-0701", "AC-0702", "AC-0703", "AC-0704",
                "AC-0705", "AC-0706", "AC-0707", "AC-0708",
            ],
            "exposure": 2839208.26,
        },
    },
    {
        "id": "ring_e",
        "name": "Synthetic — Ring E",
        "description": "6 accounts · ~$500 structuring · NO timing tell · loose cohort — stress test.",
        "path": str(REPO_ROOT / "data" / "test-rings" / "ring_e_hard.csv"),
        "answer_key": {
            "ring": [
                "AC-0800", "AC-0801", "AC-0802", "AC-0803", "AC-0804", "AC-0805",
            ],
            "exposure": 83487.45,
        },
    },
    {
        "id": "clean",
        "name": "Synthetic — Clean (control)",
        "description": "Control · no coordinated ring · checks the false-positive guard.",
        "path": str(REPO_ROOT / "data" / "test-rings" / "clean_control.csv"),
        "answer_key": {"ring": []},
    },
]

# Runtime-uploaded datasets (id -> meta).
_uploaded: dict[str, dict] = {}
_active_id: str = _PRELOADED[0]["id"]


def _all() -> list[dict]:
    return _PRELOADED + list(_uploaded.values())


def find(dataset_id: str) -> dict | None:
    return next((d for d in _all() if d["id"] == dataset_id), None)


def list_datasets() -> list[dict]:
    """Public listing with light summary stats (no answer keys leaked)."""
    out = []
    for d in _all():
        item = {
            "id": d["id"],
            "name": d["name"],
            "description": d.get("description", ""),
            "active": d["id"] == _active_id,
            "uploaded": d["id"] in _uploaded,
        }
        try:
            item["summary"] = loader.load_dataset(d["path"]).summary()
        except Exception as e:  # corrupt/missing file shouldn't break the list
            item["error"] = str(e)
        out.append(item)
    return out


def select(dataset_id: str) -> dict:
    """Make a dataset active. Returns its summary."""
    d = find(dataset_id)
    if d is None:
        raise KeyError(f"unknown dataset '{dataset_id}'")
    data = loader.set_active_dataset(d["path"])
    global _active_id
    _active_id = dataset_id
    return data.summary()


def active() -> dict:
    d = find(_active_id) or _PRELOADED[0]
    return {"id": d["id"], "name": d["name"]}


def answer_key() -> dict | None:
    d = find(_active_id)
    return d.get("answer_key") if d else None


def register_upload(filename: str, content: bytes) -> dict:
    """Validate + persist an uploaded CSV, register and activate it."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe = Path(filename).name or "dataset.csv"
    dest = UPLOAD_DIR / safe
    dest.write_bytes(content)
    # Validate by parsing (raises SchemaError on bad schema) — also evicts a
    # stale cache entry so a re-upload of the same name re-parses.
    loader._cache.pop(str(dest), None)
    summary = loader.load_dataset(dest).summary()
    ds_id = f"upload:{safe}"
    _uploaded[ds_id] = {
        "id": ds_id,
        "name": safe,
        "description": "Uploaded dataset.",
        "path": str(dest),
    }
    select(ds_id)
    return {"id": ds_id, "summary": summary}
