"""Temporal analytics: when do transactions happen, and which accounts cluster
their activity in unusual (low-traffic) hours?"""
from __future__ import annotations

import pandas as pd

from app.data.loader import get_data


def hour_histogram(account_ids: list[str] | None = None) -> dict:
    """Distribution of transactions across the 24 hours of the day.

    Args:
        account_ids: restrict to these accounts; None = whole population.
    """
    data = get_data()
    df = data.df
    if account_ids:
        df = df[df["account_id"].isin(account_ids)]

    counts = df["hour"].value_counts().sort_index()
    hist = {int(h): int(counts.get(h, 0)) for h in range(24)}
    total = int(sum(hist.values()))
    return {
        "scope": account_ids or "all_accounts",
        "total_txns": total,
        "histogram": hist,
        "busiest_hours": sorted(hist, key=lambda h: -hist[h])[:3],
        "quietest_hours": sorted(hist, key=lambda h: hist[h])[:3],
    }


def off_hours_accounts(
    start_hour: int = 0, end_hour: int = 6, min_ratio: float = 0.5, min_txns: int = 5
) -> dict:
    """Accounts whose activity is heavily concentrated in a quiet night window.

    Args:
        start_hour, end_hour: night window [start, end).
        min_ratio: minimum fraction of an account's txns that fall in-window.
        min_txns: ignore accounts with fewer than this many transactions.
    """
    data = get_data()
    df = data.df
    in_window = df["hour"].between(start_hour, end_hour - 1)

    rows = []
    for acc, g in df.groupby("account_id"):
        n = len(g)
        if n < min_txns:
            continue
        night = int(in_window[g.index].sum())
        ratio = night / n
        if ratio >= min_ratio:
            rows.append(
                {
                    "account_id": acc,
                    "txns": n,
                    "night_txns": night,
                    "night_ratio": round(ratio, 3),
                }
            )
    rows.sort(key=lambda r: (-r["night_ratio"], -r["night_txns"]))

    # Population baseline for comparison.
    pop_ratio = round(float(in_window.mean()), 3)
    return {
        "window": f"{start_hour:02d}:00-{end_hour:02d}:00",
        "population_night_ratio": pop_ratio,
        "flagged_count": len(rows),
        "accounts": rows,
        "interpretation": (
            f"Population does ~{pop_ratio:.0%} of activity in this window; the "
            "listed accounts are far above that, suggesting automated/coordinated "
            "off-hours behaviour."
        ),
    }


def synchronized_accounts(
    min_share: float = 0.6, top_hours: int = 2, min_txns: int = 5
) -> dict:
    """Accounts whose activity is abnormally concentrated in a few hours.

    Adaptive and time-agnostic: rather than a fixed night window, it flags
    accounts where the busiest `top_hours` hours hold at least `min_share` of all
    their activity — the signature of scripted, coordinated transfers, whatever
    hour the ring happens to use. The population baseline is reported for context.
    """
    data = get_data()
    df = data.df

    rows = []
    pop_shares = []
    for acc, g in df.groupby("account_id"):
        if len(g) < min_txns:
            continue
        vc = g["hour"].value_counts(normalize=True)
        share = float(vc.head(top_hours).sum())
        pop_shares.append(share)
        if share >= min_share:
            dominant = sorted(g["hour"].value_counts().head(top_hours).index.tolist())
            rows.append(
                {
                    "account_id": acc,
                    "txns": int(len(g)),
                    "top_hours_share": round(share, 3),
                    "dominant_hours": [int(h) for h in dominant],
                }
            )
    rows.sort(key=lambda r: -r["top_hours_share"])
    import statistics

    baseline = round(statistics.median(pop_shares), 3) if pop_shares else 0.0
    return {
        "top_hours": top_hours,
        "min_share": min_share,
        "population_median_share": baseline,
        "flagged_count": len(rows),
        "accounts": rows,
        "interpretation": (
            f"A typical account spreads activity (median top-{top_hours}-hour share "
            f"≈{baseline:.0%}). The flagged accounts cram ≥{min_share:.0%} of their "
            "transactions into a couple of hours — coordinated, scripted timing."
        ),
    }


def time_clustering(account_ids: list[str]) -> dict:
    """How tightly a set of accounts cluster in time — are their transfers
    synchronized (same hours, same days)?"""
    data = get_data()
    df = data.df[data.df["account_id"].isin(account_ids)]
    if df.empty:
        return {"accounts": account_ids, "txns": 0}

    hour_counts = df["hour"].value_counts()
    dominant_hours = sorted(hour_counts.index[:3].tolist())
    dominant_share = round(float(hour_counts.head(3).sum() / len(df)), 3)
    return {
        "accounts": account_ids,
        "txns": int(len(df)),
        "dominant_hours": [int(h) for h in dominant_hours],
        "dominant_hours_share": dominant_share,
        "distinct_hours_used": int(df["hour"].nunique()),
        "interpretation": (
            "A high share of activity concentrated in a few hours indicates "
            "scripted, coordinated timing rather than organic spending."
        ),
    }
