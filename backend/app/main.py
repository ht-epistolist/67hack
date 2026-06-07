"""FastAPI app: serves the transaction graph + data summary over REST, runs the
investigation, and streams every agent event to the UI over a WebSocket.
"""
from __future__ import annotations

import asyncio
import hashlib
import math

import networkx as nx
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import llm
from app.agents.orchestrator import run_investigation
from app.data import datasets
from app.data.loader import SchemaError, get_data
from app.events import bus

app = FastAPI(title="frtc — multi-agent fraud investigator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Center + radii for the deterministic graph layout.
_CENTER = (480.0, 360.0)


def _hash_angle(seed: str) -> float:
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    return (h % 3600) / 3600 * 2 * math.pi


def _open(data, acc):
    od = data.open_date(acc)
    return od.date().isoformat() if od is not None else None


def build_graph_payload(context_sample: int = 48) -> dict:
    """Nodes (with precomputed positions) + edges for the React Flow graph.

    Clean, centered, concentric layout: the account-to-account transfer ring sits
    on an inner circle (connected members kept adjacent), with a thin sample of
    ordinary accounts on an outer ring as context. Symmetric about the center so
    the view fits neatly with no dead space.
    """
    data = get_data()
    df = data.df
    a2a = df[df["is_a2a"]]

    pair = (
        a2a.groupby(["account_id", "counterparty_id"])["amount"]
        .agg(["size", "sum"])
        .reset_index()
    )
    network_nodes = set(pair["account_id"]) | set(pair["counterparty_id"])
    originators = set(df["account_id"].unique())

    from app.tools.account_tools import recent_cohort

    cohort = {a["account_id"] for a in recent_cohort(60)["accounts"]}
    inner_set = network_nodes | cohort

    # Order inner nodes by connected component so transfer chords stay short.
    g = nx.Graph()
    g.add_nodes_from(inner_set)
    for _, r in pair.iterrows():
        g.add_edge(r["account_id"], r["counterparty_id"])
    order: list[str] = []
    for comp in sorted(nx.connected_components(g), key=lambda c: (-len(c), min(c))):
        order.extend(sorted(comp))
    for n in sorted(inner_set):
        if n not in order:
            order.append(n)

    cx, cy = _CENTER
    nodes = []
    seen = set()

    # Inner ring — the suspicious network.
    r_in = 155
    n_in = max(1, len(order))
    for i, acc in enumerate(order):
        ang = 2 * math.pi * i / n_in - math.pi / 2
        nodes.append(
            {
                "id": acc,
                "x": float(cx + math.cos(ang) * r_in),
                "y": float(cy + math.sin(ang) * r_in),
                "in_network": acc in network_nodes,
                "receiver_only": acc not in originators,
                "recent": acc in cohort,
                "open_date": _open(data, acc),
            }
        )
        seen.add(acc)

    # Outer ring — a thin, even sample of ordinary accounts for context.
    others = sorted(a for a in data.accounts if a not in seen)
    step = max(1, len(others) // context_sample)
    sample = others[::step][:context_sample]
    for i, acc in enumerate(sample):
        ang = 2 * math.pi * i / max(1, len(sample))
        rad = 320 + (_hash_angle(acc) / (2 * math.pi)) * 70
        nodes.append(
            {
                "id": acc,
                "x": float(cx + math.cos(ang) * rad),
                "y": float(cy + math.sin(ang) * rad),
                "in_network": False,
                "receiver_only": False,
                "recent": acc in cohort,
                "open_date": _open(data, acc),
            }
        )

    edges = [
        {
            "id": f"{r['account_id']}->{r['counterparty_id']}",
            "source": r["account_id"],
            "target": r["counterparty_id"],
            "count": int(r["size"]),
            "amount": round(float(r["sum"]), 2),
        }
        for _, r in pair.iterrows()
    ]
    return {"nodes": nodes, "edges": edges}


@app.get("/api/health")
async def health():
    return {"status": "ok", "llm_enabled": llm.available()}


@app.get("/api/summary")
async def summary():
    return {
        **get_data().summary(),
        "llm_enabled": llm.available(),
        "dataset": datasets.active(),
    }


@app.get("/api/datasets")
async def list_datasets():
    return {"datasets": datasets.list_datasets(), "active": datasets.active()}


@app.post("/api/datasets/select")
async def select_dataset(body: dict):
    ds_id = body.get("id")
    try:
        summary = datasets.select(ds_id)
    except KeyError:
        raise HTTPException(404, f"unknown dataset '{ds_id}'")
    bus.reset()  # clear any prior investigation
    return {"selected": ds_id, "summary": summary, "dataset": datasets.active()}


@app.post("/api/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)):
    content = await file.read()
    try:
        result = datasets.register_upload(file.filename or "dataset.csv", content)
    except SchemaError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(400, f"could not read CSV: {e}")
    bus.reset()
    return {**result, "dataset": datasets.active()}


@app.get("/api/graph")
async def graph():
    return build_graph_payload()


@app.get("/api/rows")
async def rows(offset: int = 0, limit: int = 50):
    """Paginated raw transactions for the data-table view."""
    data = get_data()
    cols = [
        "txn_id", "account_id", "counterparty_id", "amount", "timestamp",
        "merchant_category", "device_id", "ip_region", "account_open_date",
    ]
    total = int(len(data.df))
    limit = max(1, min(limit, 200))
    offset = max(0, min(offset, total))
    page = data.df.iloc[offset : offset + limit]
    out_rows = []
    for _, r in page.iterrows():
        out_rows.append([
            r["txn_id"], r["account_id"], r["counterparty_id"],
            round(float(r["amount"]), 2),
            r["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            r["merchant_category"], r["device_id"], r["ip_region"],
            r["account_open_date"].strftime("%Y-%m-%d"),
        ])
    return {"columns": cols, "rows": out_rows, "total": total, "offset": offset, "limit": limit}


@app.get("/api/overview")
async def overview():
    """Aggregates for the initial data panel (visible before any investigation)."""
    from app.tools import account_tools, amount_tools, temporal_tools

    data = get_data()
    df = data.df
    hours = temporal_tools.hour_histogram()["histogram"]
    cats = df["merchant_category"].value_counts().to_dict()
    regions = df["ip_region"].value_counts().to_dict()
    amt = amount_tools.amount_overview()
    cohort = account_tools.recent_cohort(60)
    night = int(df["hour"].between(0, 5).sum())
    return {
        "hours": [{"hour": h, "count": int(hours.get(h, 0))} for h in range(24)],
        "categories": [{"name": k, "count": int(v)} for k, v in cats.items()],
        "regions": [{"name": k, "count": int(v)} for k, v in regions.items()],
        "amounts": amt,
        "night_txns": night,
        "night_share": round(night / len(df), 3),
        "cohort_size": cohort["cohort_size"],
        "cohort_accounts": [a["account_id"] for a in cohort["accounts"]],
        "window_days": (data.window_end - data.window_start).days,
    }


@app.get("/api/report")
async def report():
    """The most recent verdict from the event history (if any)."""
    for evt in reversed(bus.history):
        if evt["type"] == "verdict":
            return evt
    return {"status": "no_investigation_yet"}


@app.post("/api/investigate")
async def investigate():
    # Fire-and-forget; progress streams over the WebSocket.
    asyncio.create_task(run_investigation(fresh=True))
    return {"started": True}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    q = bus.subscribe()
    try:
        # Replay history so a late client sees the whole investigation.
        for evt in list(bus.history):
            await websocket.send_json(evt)
        while True:
            evt = await q.get()
            await websocket.send_json(evt)
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(q)
