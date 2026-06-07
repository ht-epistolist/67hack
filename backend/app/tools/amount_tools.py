"""Amount analytics: structuring / threshold-hugging and repeated near-identical
amounts — the signatures of transfers deliberately kept under alert limits."""
from __future__ import annotations

import numpy as np

from app.data.loader import get_data


def amount_overview(account_ids: list[str] | None = None) -> dict:
    """Percentile summary of transaction amounts for a scope."""
    data = get_data()
    df = data.df
    if account_ids:
        df = df[df["account_id"].isin(account_ids)]
    amts = df["amount"].to_numpy()
    if len(amts) == 0:
        return {"scope": account_ids, "count": 0}
    return {
        "scope": account_ids or "all_accounts",
        "count": int(len(amts)),
        "min": round(float(amts.min()), 2),
        "p50": round(float(np.percentile(amts, 50)), 2),
        "p95": round(float(np.percentile(amts, 95)), 2),
        "p99": round(float(np.percentile(amts, 99)), 2),
        "max": round(float(amts.max()), 2),
        "mean": round(float(amts.mean()), 2),
    }


def _round_thresholds(max_amount: float) -> list[float]:
    """Plausible round 'alert' thresholds (1/2/5 x 10^k) up to the data's range."""
    out: list[float] = []
    k = 2  # start at 100
    while 10**k <= max_amount * 2:
        for m in (1, 2, 5):
            t = m * (10**k)
            if 100 <= t <= max_amount * 3:
                out.append(float(t))
        k += 1
    return sorted(set(out))


def threshold_hugging(
    min_in_band: int = 5, band_ratio: float = 0.5, account_ids: list[str] | None = None
) -> dict:
    """Accounts that keep many transactions just under a round alert threshold.

    Adaptive: instead of a fixed band, it scans plausible round thresholds
    (… $1k, $2k, $5k, $10k …) and, per account, finds the tightest ceiling T the
    account *never crosses* while still packing many transactions into
    [band_ratio·T, T). This catches structuring at whatever level a given ring
    uses (≈$890 here, ≈$4.8k elsewhere) without hard-coding the amount.

    Args:
        min_in_band: minimum in-band transactions to flag an account.
        band_ratio: lower edge of the band as a fraction of the threshold.
        account_ids: optional subset; omit for all accounts.
    """
    data = get_data()
    df = data.df
    if account_ids:
        df = df[df["account_id"].isin(account_ids)]
    if df.empty:
        return {"flagged_count": 0, "accounts": []}

    thresholds = _round_thresholds(float(df["amount"].max()))
    rows = []
    for acc, g in df.groupby("account_id"):
        amts = g["amount"]
        amax = float(amts.max())
        best = None
        for t in thresholds:
            if amax >= t:  # only thresholds this account never crosses
                continue
            in_band = int(((amts >= band_ratio * t) & (amts < t)).sum())
            if in_band >= min_in_band and (best is None or t < best["threshold"]):
                band_amts = amts[(amts >= band_ratio * t) & (amts < t)]
                best = {
                    "account_id": acc,
                    "threshold": t,
                    "band": [round(band_ratio * t, 2), t],
                    "in_band_txns": in_band,
                    "band_mean": round(float(band_amts.mean()), 2),
                    "band_std": round(float(band_amts.std(ddof=0)), 2),
                    "share_of_account": round(in_band / len(g), 3),
                }
        if best:
            rows.append(best)
    rows.sort(key=lambda r: -r["in_band_txns"])
    return {
        "flagged_count": len(rows),
        "accounts": rows,
        "interpretation": (
            "Accounts that repeatedly transact just below a round threshold they "
            "never cross are deliberately structuring to stay under reporting "
            "limits. The threshold is detected per account, not assumed."
        ),
    }


def repeated_amounts(account_id: str, tolerance: float = 5.0) -> dict:
    """Detect clusters of near-identical repeated amounts for one account."""
    data = get_data()
    g = data.account_txns(account_id)
    if g.empty:
        return {"account_id": account_id, "txns": 0, "clusters": []}

    amts = sorted(g["amount"].tolist())
    clusters = []
    current = [amts[0]]
    for a in amts[1:]:
        if a - current[-1] <= tolerance:
            current.append(a)
        else:
            if len(current) >= 3:
                clusters.append(current)
            current = [a]
    if len(current) >= 3:
        clusters.append(current)

    return {
        "account_id": account_id,
        "txns": int(len(g)),
        "repeated_clusters": [
            {
                "count": len(c),
                "min": round(min(c), 2),
                "max": round(max(c), 2),
                "mean": round(sum(c) / len(c), 2),
            }
            for c in clusters
        ],
        "interpretation": (
            "Tight clusters of repeated amounts suggest scripted transfers of a "
            "fixed sum rather than organic purchases."
        ),
    }
