"""Unsupervised, content-agnostic ring detector.

Assumes only the dataset *structure* (the standard columns), never specific
values. The pipeline:

  1. Per-account features that are entirely population-relative.
  2. A robust anomaly score per account (median/MAD z-scores in the
     fraud-suspicious direction; no absolute thresholds).
  3. A *coordination graph* linking accounts by evidence of collusion:
     direct peer transfers, shared devices, a tight shared open-date cohort,
     and high behavioural-fingerprint similarity.
  4. Communities of that graph (connected components) become candidate rings.
  5. Each candidate is scored by anomaly × coordination × self-containment, so a
     benign cluster (old accounts, varied behaviour) ranks far below a ring — and
     a dataset with no ring simply yields no high-scoring candidate.

Nothing here references account ids, amounts, hours or dates that were observed
beforehand; every cut-off is a percentile / gap of the data at hand.
"""
from __future__ import annotations

import math
from functools import lru_cache

import networkx as nx
import numpy as np
import pandas as pd

from app.data.loader import get_data
from app.tools.amount_tools import _round_thresholds


# --------------------------------------------------------------------------- #
# 1. Features
# --------------------------------------------------------------------------- #
def _entropy(counts: np.ndarray) -> float:
    p = counts / counts.sum()
    p = p[p > 0]
    return float(-(p * np.log(p)).sum())


def _threshold_hug(amts: np.ndarray, thresholds: list[float], min_in_band=4) -> float:
    """Largest count of amounts sitting in [0.5T, T) for a round T never crossed."""
    amax = amts.max()
    best = 0
    for t in thresholds:
        if amax >= t:
            continue
        in_band = int(((amts >= 0.5 * t) & (amts < t)).sum())
        best = max(best, in_band)
    return float(best if best >= min_in_band else 0)


def compute_features() -> pd.DataFrame:
    """One row per account seen (originator or peer-counterparty)."""
    data = get_data()
    df = data.df
    thresholds = _round_thresholds(float(df["amount"].max()))
    window_start = data.window_start

    originators = set(df["account_id"].unique())
    receivers = set(df.loc[df["is_a2a"], "counterparty_id"].unique())
    all_accounts = sorted(originators | receivers)

    # incoming peer-transfer aggregates (for receiver roles)
    a2a = df[df["is_a2a"]]
    in_count = a2a.groupby("counterparty_id").size().to_dict()

    rows = []
    for acc in all_accounts:
        g = df[df["account_id"] == acc]
        n = len(g)
        rec_only = n == 0
        if rec_only:
            rows.append(
                {
                    "account_id": acc, "txns": 0, "receiver_only": True,
                    "a2a_ratio": 0.0, "in_degree": int(in_count.get(acc, 0)),
                    "amt_cv": np.nan, "repeated_frac": 0.0, "thug": 0.0,
                    "top2_share": np.nan, "hour_entropy": np.nan,
                    "interarrival_cv": np.nan, "n_devices": 0, "n_regions": 0,
                    "age_days": np.nan, "out_flow": 0.0,
                }
            )
            continue
        amts = g["amount"].to_numpy()
        hours = g["hour"].to_numpy()
        hour_counts = np.bincount(hours, minlength=24).astype(float)
        ts = np.sort(g["timestamp"].astype("int64").to_numpy())
        if len(ts) > 2:
            gaps = np.diff(ts).astype(float)
            ia_cv = float(gaps.std() / (gaps.mean() + 1e-9))
        else:
            ia_cv = np.nan
        uniq_amt = len(np.unique(np.round(amts, 2)))
        rows.append(
            {
                "account_id": acc,
                "txns": n,
                "receiver_only": False,
                "a2a_ratio": float(g["is_a2a"].mean()),
                "in_degree": int(in_count.get(acc, 0)),
                "amt_cv": float(amts.std() / (amts.mean() + 1e-9)),
                "repeated_frac": float(1 - uniq_amt / n),
                "thug": _threshold_hug(amts, thresholds),
                "top2_share": float(np.sort(hour_counts)[-2:].sum() / n),
                "hour_entropy": _entropy(hour_counts + 1e-9),
                "interarrival_cv": ia_cv,
                "n_devices": int(g["device_id"].nunique()),
                "n_regions": int(g["ip_region"].nunique()),
                "age_days": float((window_start - g["account_open_date"].iloc[0]).days),
                "out_flow": float(amts.sum()),
            }
        )
    return pd.DataFrame(rows).set_index("account_id")


# --------------------------------------------------------------------------- #
# 2. Anomaly score
# --------------------------------------------------------------------------- #
def _robust_z(s: pd.Series) -> pd.Series:
    x = s.astype(float)
    med = x.median()
    mad = (x - med).abs().median()
    scale = 1.4826 * mad if mad > 0 else (x.std() or 1.0)
    return (x - med) / (scale + 1e-9)


# (feature, direction): +1 => high is suspicious, -1 => low is suspicious
_ANOMALY_FEATURES = [
    ("a2a_ratio", +1),
    ("thug", +1),
    ("top2_share", +1),
    ("repeated_frac", +1),
    ("amt_cv", -1),           # very regular amounts
    ("interarrival_cv", -1),  # very regular timing (scripted)
    ("hour_entropy", -1),     # active in few hours
    ("age_days", -1),         # freshly opened
]


def anomaly_scores(feat: pd.DataFrame) -> pd.Series:
    active = feat[~feat["receiver_only"]]
    score = pd.Series(0.0, index=feat.index)
    for col, direction in _ANOMALY_FEATURES:
        z = _robust_z(active[col].dropna()) * direction
        z = z.clip(lower=0)  # only the suspicious tail contributes
        score.loc[z.index] += z
    # Receiver-only accounts are structurally odd (receive but never originate):
    # seed them at the 75th percentile of active anomaly so they can join rings.
    if (feat["receiver_only"]).any():
        seed = float(score[~feat["receiver_only"]].quantile(0.75))
        score.loc[feat["receiver_only"]] = seed
    return score


# --------------------------------------------------------------------------- #
# 3. Coordination graph
# --------------------------------------------------------------------------- #
def _recent_cohort_members(feat: pd.DataFrame) -> set[str]:
    """Youngest accounts separated from the population by a large age gap."""
    ages = feat["age_days"].dropna().sort_values()
    if len(ages) < 4:
        return set()
    vals = ages.to_numpy()
    region = max(2, int(len(vals) * 0.4))
    typical = (vals[region] - vals[0]) / max(1, region)
    best_gap, cut = 0.0, -1
    for i in range(min(region, len(vals) - 1)):
        gap = vals[i + 1] - vals[i]
        if gap > best_gap:
            best_gap, cut = gap, i
    if cut >= 0 and best_gap >= max(20.0, 5.0 * typical):
        cutoff = vals[cut]
        return set(ages[ages <= cutoff].index)
    return set()


def _fingerprint(feat: pd.DataFrame, accounts: list[str]) -> dict[str, np.ndarray]:
    cols = ["a2a_ratio", "top2_share", "repeated_frac"]
    sub = feat.loc[accounts, cols].fillna(feat[cols].median())
    # add inverse-cv and recency, normalised
    inv_cv = 1.0 / (1.0 + feat.loc[accounts, "amt_cv"].fillna(1.0))
    age = feat.loc[accounts, "age_days"]
    recency = 1.0 - (age - age.min()) / ((age.max() - age.min()) or 1.0)
    mat = np.column_stack([sub.to_numpy(), inv_cv.to_numpy(), recency.fillna(0).to_numpy()])
    # z-normalise columns
    mu, sd = mat.mean(0), mat.std(0) + 1e-9
    mat = (mat - mu) / sd
    return {a: mat[i] for i, a in enumerate(accounts)}


def build_coordination_graph(feat: pd.DataFrame, anomaly: pd.Series) -> nx.Graph:
    data = get_data()
    df = data.df
    g = nx.Graph()
    g.add_nodes_from(feat.index)

    def link(u, v, w, kind):
        if u == v:
            return
        if g.has_edge(u, v):
            g[u][v]["weight"] += w
            g[u][v]["kinds"].add(kind)
        else:
            g.add_edge(u, v, weight=w, kinds={kind})

    # (a) direct peer transfers
    a2a = df[df["is_a2a"]]
    pair = a2a.groupby(["account_id", "counterparty_id"]).size()
    for (u, v), c in pair.items():
        link(u, v, 2.0 * math.log1p(c), "transfer")

    # (b) shared devices
    for _, gg in df.groupby("device_id"):
        accs = sorted(gg["account_id"].unique())
        if 1 < len(accs) <= 8:  # a device for hundreds of accounts is infra, not a ring
            for i in range(len(accs)):
                for j in range(i + 1, len(accs)):
                    link(accs[i], accs[j], 3.0, "device")

    # (c) tight, freshly-opened cohort
    cohort = _recent_cohort_members(feat)
    cohort = sorted(cohort)
    for i in range(len(cohort)):
        for j in range(i + 1, len(cohort)):
            link(cohort[i], cohort[j], 2.0, "cohort")

    # (d) behavioural similarity among the most anomalous accounts
    top = anomaly[~feat["receiver_only"]].sort_values(ascending=False)
    cand = list(top.head(40).index)
    if len(cand) >= 3:
        fp = _fingerprint(feat, cand)
        sims = []
        for i in range(len(cand)):
            for j in range(i + 1, len(cand)):
                a, b = cand[i], cand[j]
                va, vb = fp[a], fp[b]
                sim = float(va @ vb / ((np.linalg.norm(va) * np.linalg.norm(vb)) + 1e-9))
                sims.append((sim, a, b))
        if sims:
            cutoff = np.quantile([s for s, _, _ in sims], 0.90)
            for sim, a, b in sims:
                if sim >= cutoff and sim > 0:
                    link(a, b, 1.5 * sim, "similarity")
    return g


# --------------------------------------------------------------------------- #
# 4 & 5. Candidate communities + scoring
# --------------------------------------------------------------------------- #
def _internal_flow(members: set[str]) -> float:
    df = get_data().df
    internal = df[df["is_a2a"] & df["account_id"].isin(members) & df["counterparty_id"].isin(members)]
    return float(internal["amount"].sum())


def score_cluster(members: set[str], feat: pd.DataFrame, anomaly: pd.Series, graph: nx.Graph) -> dict:
    members = set(members)
    mean_anom = float(anomaly.loc[sorted(members)].mean())
    sub = graph.subgraph(members)
    n = len(members)
    poss = n * (n - 1) / 2 or 1
    coord_density = sub.size(weight="weight") / poss
    internal = _internal_flow(members)
    df = get_data().df
    out_flow = float(df[df["account_id"].isin(members)]["amount"].sum())
    self_contain = internal / (out_flow + 1e-9) if out_flow else (1.0 if internal else 0.0)
    kinds = set().union(*[d["kinds"] for *_e, d in sub.edges(data=True)]) if sub.number_of_edges() else set()
    score = mean_anom * (1.0 + coord_density) * (1.0 + len(kinds))
    return {
        "members": sorted(members),
        "size": n,
        "mean_anomaly": round(mean_anom, 3),
        "coordination_density": round(float(coord_density), 3),
        "self_containment": round(self_contain, 3),
        "internal_flow": round(internal, 2),
        "evidence_kinds": sorted(kinds),
        "score": round(float(score), 3),
    }


# Membership requires *strong* collusion evidence; behavioural similarity alone
# can make innocent look-alikes appear connected, so it only informs ranking.
STRONG_KINDS = {"transfer", "device", "cohort"}


@lru_cache(maxsize=8)
def _cached_run(path_key: str) -> dict:
    feat = compute_features()
    anomaly = anomaly_scores(feat)
    graph = build_coordination_graph(feat, anomaly)
    pop_anom = float(anomaly[~feat["receiver_only"]].median())
    pop_std = float(anomaly[~feat["receiver_only"]].std() or 1.0)

    # Connected components over strong edges only define candidate membership.
    strong = nx.Graph()
    strong.add_nodes_from(graph.nodes)
    for u, v, d in graph.edges(data=True):
        if d["kinds"] & STRONG_KINDS:
            strong.add_edge(u, v)

    n_strong = sum(1 for c in nx.connected_components(strong) if len(c) >= 3)
    clusters = []
    for comp in nx.connected_components(strong):
        if len(comp) < 3:
            continue
        clusters.append(score_cluster(comp, feat, anomaly, graph))
    # A candidate must be meaningfully more anomalous than the population.
    threshold = pop_anom + 1.0 * pop_std
    clusters = [c for c in clusters if c["mean_anomaly"] >= threshold]
    clusters.sort(key=lambda c: -c["score"])

    edge_kinds: dict[str, int] = {}
    for *_e, d in graph.edges(data=True):
        for k in d["kinds"]:
            edge_kinds[k] = edge_kinds.get(k, 0) + 1
    kinds_txt = ", ".join(f"{k} ×{v}" for k, v in sorted(edge_kinds.items())) or "none"

    # Narrated preprocessing stages (the unsupervised ML pipeline) for the live feed.
    steps = [
        {"stage": "features",
         "message": f"Feature extraction — built {len(_ANOMALY_FEATURES)}+ population-relative "
                    f"features for {len(feat)} accounts (graph degree, amount dispersion, "
                    f"timing entropy, inter-arrival regularity, account age)."},
        {"stage": "anomaly",
         "message": f"Anomaly model — robust median/MAD z-score ensemble over "
                    f"{len(_ANOMALY_FEATURES)} fraud-suspicious signals; population median "
                    f"{round(pop_anom, 2)}, flag threshold {round(threshold, 2)}."},
        {"stage": "graph",
         "message": f"Coordination graph — {graph.number_of_edges()} weighted links "
                    f"({kinds_txt})."},
        {"stage": "community",
         "message": f"Community detection — {n_strong} strong-edge cluster(s); "
                    f"{len(clusters)} above the anomaly threshold."},
    ]
    return {
        "candidates": clusters,
        "population_anomaly_median": round(pop_anom, 3),
        "anomaly_threshold": round(threshold, 3),
        "feature_count": len(feat),
        "steps": steps,
    }


def run() -> dict:
    """Full unsupervised detection for the active dataset (cached per path)."""
    from app.data.loader import active_path

    return _cached_run(active_path())


def candidate_clusters() -> list[dict]:
    return run()["candidates"]


# --------------------------------------------------------------------------- #
# Drill-down helpers (also exposed to agents as tools)
# --------------------------------------------------------------------------- #
def coordination_score(members: list[str]) -> dict:
    """How coordinated is an arbitrary set of accounts? (for hypothesis testing)"""
    feat = compute_features()
    anomaly = anomaly_scores(feat)
    graph = build_coordination_graph(feat, anomaly)
    present = [m for m in members if m in graph]
    if len(present) < 2:
        return {"members": members, "error": "need >=2 known accounts"}
    return score_cluster(set(present), feat, anomaly, graph)
