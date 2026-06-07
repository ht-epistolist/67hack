"""Account-level analytics: full profiles, newly-opened cohorts, device sharing,
and peer comparison against population baselines."""
from __future__ import annotations

import pandas as pd

from app.data.loader import get_data


def account_profile(account_id: str) -> dict:
    """A comprehensive behavioural profile for a single account, including
    receiver-only accounts (which have no originated txns)."""
    data = get_data()
    sent = data.account_txns(account_id)
    received = data.df[
        (data.df["is_a2a"]) & (data.df["counterparty_id"] == account_id)
    ]

    if sent.empty and received.empty:
        return {"account_id": account_id, "exists": False}

    open_date = data.open_date(account_id)
    profile = {
        "account_id": account_id,
        "exists": True,
        "account_open_date": open_date.date().isoformat() if open_date is not None else None,
        "account_age_days_at_window_start": (
            int((data.window_start - open_date).days) if open_date is not None else None
        ),
        "originated_txns": int(len(sent)),
        "received_transfers": int(len(received)),
        "received_total": round(float(received["amount"].sum()), 2),
    }

    if not sent.empty:
        a2a = sent[sent["is_a2a"]]
        profile.update(
            {
                "devices": sorted(sent["device_id"].unique().tolist()),
                "ip_regions": sorted(sent["ip_region"].unique().tolist()),
                "merchant_categories": sorted(sent["merchant_category"].unique().tolist()),
                "total_sent": round(float(sent["amount"].sum()), 2),
                "a2a_txns": int(len(a2a)),
                "a2a_ratio": round(len(a2a) / len(sent), 3),
                "a2a_counterparties": sorted(a2a["counterparty_id"].unique().tolist()),
                "night_txns": int(sent["hour"].between(0, 5).sum()),
                "night_ratio": round(float(sent["hour"].between(0, 5).mean()), 3),
                "mean_amount": round(float(sent["amount"].mean()), 2),
                "first_txn": sent["timestamp"].min().isoformat(),
                "last_txn": sent["timestamp"].max().isoformat(),
            }
        )
    return profile


def _adaptive_age_cutoff(ages_sorted: list[int]) -> int | None:
    """Find a 'freshly-opened cohort' as the youngest accounts separated from the
    rest by a large gap in account age. Returns the inclusive age cutoff, or None
    if there's no clear cohort."""
    n = len(ages_sorted)
    if n < 4:
        return None
    region = max(2, int(n * 0.4))  # only look for the break among the youngest 40%
    typical = (ages_sorted[region] - ages_sorted[0]) / max(1, region)
    best_gap, cut_idx = 0.0, -1
    for i in range(min(region, n - 1)):
        gap = ages_sorted[i + 1] - ages_sorted[i]
        if gap > best_gap:
            best_gap, cut_idx = gap, i
    # Require the break to be much larger than the typical spacing in the region.
    if cut_idx >= 0 and best_gap >= max(20.0, 5.0 * typical):
        return ages_sorted[cut_idx]
    return None


def recent_cohort(window_days: int | None = None) -> dict:
    """Freshly-opened account cohort — a classic synthetic/bust-out signal.

    Adaptive by default: detects the cluster of youngest accounts separated from
    the rest of the population by a large gap in account age (so it works whatever
    the absolute open dates are). Pass `window_days` to force a fixed cutoff
    (accounts opened within N days before the observation window).
    """
    data = get_data()
    opens = data.df.groupby("account_id")["account_open_date"].first()
    ages = {
        acc: int((data.window_start - od).days) for acc, od in opens.items()
    }

    if window_days is not None:
        cutoff_age = window_days
        method = f"fixed ≤{window_days}d before window"
    else:
        cutoff_age = _adaptive_age_cutoff(sorted(ages.values()))
        method = "adaptive age-gap"

    rows = []
    if cutoff_age is not None:
        for acc, age in ages.items():
            if age <= cutoff_age:
                g = data.account_txns(acc)
                rows.append(
                    {
                        "account_id": acc,
                        "open_date": opens[acc].date().isoformat(),
                        "age_days_at_window": age,
                        "txns": int(len(g)),
                        "a2a_ratio": round(float(g["is_a2a"].mean()), 3),
                    }
                )
    rows.sort(key=lambda r: r["age_days_at_window"])
    return {
        "method": method,
        "age_cutoff_days": cutoff_age,
        "data_window_start": data.window_start.date().isoformat(),
        "cohort_size": len(rows),
        "accounts": rows,
        "interpretation": (
            "A tight cluster of accounts opened just before the data window — far "
            "more recent than the rest of the population — that is already active "
            "is disproportionately likely to be a coordinated/synthetic cohort."
        ),
    }


def device_sharing() -> dict:
    """Devices used by more than one account (shared-infrastructure signal)."""
    data = get_data()
    dev_to_accounts: dict[str, set] = {}
    for dev, g in data.df.groupby("device_id"):
        accs = set(g["account_id"].unique())
        if len(accs) > 1:
            dev_to_accounts[dev] = accs
    shared = [
        {"device_id": d, "accounts": sorted(a), "account_count": len(a)}
        for d, a in dev_to_accounts.items()
    ]
    shared.sort(key=lambda x: -x["account_count"])
    return {
        "shared_device_count": len(shared),
        "devices": shared,
        "interpretation": (
            "A single device driving multiple accounts indicates one operator "
            "controlling several identities."
        ),
    }


def peer_comparison(account_id: str) -> dict:
    """Compare an account's key metrics to population baselines (how unusual)."""
    data = get_data()
    df = data.df
    g = data.account_txns(account_id)
    if g.empty:
        return {"account_id": account_id, "exists": False}

    per_acc = df.groupby("account_id").agg(
        txns=("amount", "size"),
        a2a_ratio=("is_a2a", "mean"),
        night_ratio=("hour", lambda s: s.between(0, 5).mean()),
        mean_amount=("amount", "mean"),
    )

    def z(metric: str, value: float) -> float:
        col = per_acc[metric]
        std = col.std(ddof=0)
        return round(float((value - col.mean()) / std), 2) if std else 0.0

    return {
        "account_id": account_id,
        "exists": True,
        "metrics": {
            "a2a_ratio": {
                "value": round(float(g["is_a2a"].mean()), 3),
                "population_mean": round(float(per_acc["a2a_ratio"].mean()), 3),
                "z_score": z("a2a_ratio", float(g["is_a2a"].mean())),
            },
            "night_ratio": {
                "value": round(float(g["hour"].between(0, 5).mean()), 3),
                "population_mean": round(float(per_acc["night_ratio"].mean()), 3),
                "z_score": z("night_ratio", float(g["hour"].between(0, 5).mean())),
            },
        },
        "interpretation": "z-scores above ~3 mark the account as a strong outlier.",
    }
