"""Drill-down investigation tools — give agents real freedom to examine the
candidate cluster: compare accounts, expand a suspect's neighborhood, inspect
shared infrastructure, and score the coordination of an arbitrary set.
"""
from __future__ import annotations

from app.data.loader import get_data
from app.engine import detector


def candidate_overview() -> dict:
    """The unsupervised engine's candidate ring(s) for the active dataset."""
    out = detector.run()
    return {
        "accounts_scanned": out["feature_count"],
        "anomaly_threshold": out["anomaly_threshold"],
        "candidate_count": len(out["candidates"]),
        "candidates": out["candidates"],
    }


def compare_accounts(account_ids: list[str]) -> dict:
    """Side-by-side behavioural profile of a set of accounts (spot the pattern)."""
    data = get_data()
    df = data.df
    rows = []
    for acc in account_ids:
        g = df[df["account_id"] == acc]
        received = df[(df["is_a2a"]) & (df["counterparty_id"] == acc)]
        if g.empty:
            rows.append(
                {"account_id": acc, "originates": False,
                 "received_transfers": int(len(received)),
                 "received_total": round(float(received["amount"].sum()), 2)}
            )
            continue
        od = data.open_date(acc)
        rows.append(
            {
                "account_id": acc,
                "originates": True,
                "txns": int(len(g)),
                "a2a_ratio": round(float(g["is_a2a"].mean()), 3),
                "top_hours": sorted(g["hour"].value_counts().head(2).index.tolist()),
                "amount_median": round(float(g["amount"].median()), 2),
                "amount_max": round(float(g["amount"].max()), 2),
                "devices": sorted(g["device_id"].unique().tolist()),
                "regions": sorted(g["ip_region"].unique().tolist()),
                "open_date": od.date().isoformat() if od is not None else None,
            }
        )
    return {"accounts": rows}


def account_neighborhood(account_id: str) -> dict:
    """An account's transfer counterparties (both directions) + device-mates."""
    data = get_data()
    df = data.df
    out = df[(df["account_id"] == account_id) & df["is_a2a"]]
    inc = df[(df["is_a2a"]) & (df["counterparty_id"] == account_id)]
    devices = df[df["account_id"] == account_id]["device_id"].unique().tolist()
    device_mates = sorted(
        set(df[df["device_id"].isin(devices)]["account_id"].unique()) - {account_id}
    )
    return {
        "account_id": account_id,
        "sends_to": sorted(out["counterparty_id"].unique().tolist()),
        "receives_from": sorted(inc["account_id"].unique().tolist()),
        "device_mates": device_mates,
        "sent_total": round(float(out["amount"].sum()), 2),
        "received_total": round(float(inc["amount"].sum()), 2),
    }


def shared_infrastructure(account_ids: list[str]) -> dict:
    """Devices / IP regions shared across a set of accounts (collusion evidence)."""
    data = get_data()
    df = data.df[data.df["account_id"].isin(account_ids)]
    dev = df.groupby("device_id")["account_id"].nunique()
    shared_dev = sorted(dev[dev > 1].index.tolist())
    return {
        "accounts": account_ids,
        "shared_devices": shared_dev,
        "distinct_devices": int(df["device_id"].nunique()),
        "regions_used": sorted(df["ip_region"].unique().tolist()),
        "interpretation": (
            "Accounts sharing a device are almost certainly one operator; a single "
            "region across supposedly independent customers is corroborating."
        ),
    }


def coordination_score(account_ids: list[str]) -> dict:
    """Score how coordinated an arbitrary set of accounts is (hypothesis test)."""
    return detector.coordination_score(account_ids)
