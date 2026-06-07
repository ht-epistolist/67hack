"""Network / graph analytics over the account-to-account transfer subgraph.

These are deterministic and general: they describe the *whole* transfer network,
not a pre-baked answer. The dense, low-volume, self-contained cluster that falls
out of these metrics is what the agents reason about.
"""
from __future__ import annotations

import networkx as nx

from app.data.loader import get_data


def _transfer_edges():
    """All account->account transfers, aggregated per directed pair."""
    data = get_data()
    a2a = data.df[data.df["is_a2a"]]
    grouped = (
        a2a.groupby(["account_id", "counterparty_id"])
        .agg(txn_count=("amount", "size"), total_amount=("amount", "sum"))
        .reset_index()
    )
    return grouped


def build_transfer_graph(min_txns: int = 1) -> dict:
    """The directed account-to-account transfer network.

    Args:
        min_txns: only include edges with at least this many transfers.
    Returns nodes, directed edges (with txn_count + total_amount), and summary
    stats describing how self-contained the network is.
    """
    edges_df = _transfer_edges()
    edges_df = edges_df[edges_df["txn_count"] >= min_txns]

    nodes: set[str] = set()
    edges = []
    for _, row in edges_df.iterrows():
        src, dst = row["account_id"], row["counterparty_id"]
        nodes.add(src)
        nodes.add(dst)
        edges.append(
            {
                "source": src,
                "target": dst,
                "txn_count": int(row["txn_count"]),
                "total_amount": round(float(row["total_amount"]), 2),
            }
        )

    total_volume = round(sum(e["total_amount"] for e in edges), 2)
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": sorted(nodes),
        "edges": sorted(edges, key=lambda e: -e["total_amount"]),
        "total_transfer_volume": total_volume,
        "note": (
            "Counterparties prefixed AC- are bank accounts (peer transfers); "
            "MR- counterparties are merchants and are excluded here."
        ),
    }


def find_receiver_only_accounts() -> dict:
    """Accounts that RECEIVE peer transfers but never originate any transaction.

    Classic mule signature: they exist only as transfer destinations.
    """
    data = get_data()
    originators = set(data.df["account_id"].unique())
    receivers = set(data.df.loc[data.df["is_a2a"], "counterparty_id"].unique())
    receiver_only = sorted(receivers - originators)

    details = []
    for acc in receiver_only:
        incoming = data.df[
            (data.df["is_a2a"]) & (data.df["counterparty_id"] == acc)
        ]
        details.append(
            {
                "account_id": acc,
                "incoming_txns": int(len(incoming)),
                "incoming_total": round(float(incoming["amount"].sum()), 2),
                "senders": sorted(incoming["account_id"].unique().tolist()),
            }
        )
    return {
        "receiver_only_count": len(receiver_only),
        "accounts": details,
        "interpretation": (
            "Accounts with incoming peer transfers but zero originated activity "
            "behave like collection mules."
        ),
    }


def detect_layering() -> dict:
    """Accounts that both receive AND re-send peer transfers (pass-through hops)."""
    edges_df = _transfer_edges()
    senders = set(edges_df["account_id"])
    receivers = set(edges_df["counterparty_id"])
    intermediaries = sorted(senders & receivers)

    details = []
    for acc in intermediaries:
        received = edges_df[edges_df["counterparty_id"] == acc]["total_amount"].sum()
        sent = edges_df[edges_df["account_id"] == acc]["total_amount"].sum()
        details.append(
            {
                "account_id": acc,
                "received_total": round(float(received), 2),
                "sent_total": round(float(sent), 2),
            }
        )
    return {
        "intermediary_count": len(intermediaries),
        "accounts": details,
        "interpretation": (
            "Accounts that receive and then forward funds form layering hops "
            "used to obscure the money trail."
        ),
    }


def connected_component(account_id: str) -> dict:
    """The cluster of accounts reachable from `account_id` via transfer edges
    (treating direction as undirected) — i.e. the candidate ring around it."""
    edges_df = _transfer_edges()
    g = nx.Graph()
    for _, row in edges_df.iterrows():
        g.add_edge(row["account_id"], row["counterparty_id"])
    if account_id not in g:
        return {"account_id": account_id, "in_transfer_network": False, "members": []}
    members = sorted(nx.node_connected_component(g, account_id))

    # Total exposure = all transfer volume internal to this component.
    member_set = set(members)
    internal = edges_df[
        edges_df["account_id"].isin(member_set)
        & edges_df["counterparty_id"].isin(member_set)
    ]
    return {
        "account_id": account_id,
        "in_transfer_network": True,
        "member_count": len(members),
        "members": members,
        "internal_transfer_total": round(float(internal["total_amount"].sum()), 2),
        "internal_txn_count": int(internal["txn_count"].sum()),
    }


def transfer_network_overview() -> dict:
    """One-shot summary combining the graph + mules + layering, plus the
    connected components so an agent sees the cluster structure at a glance."""
    graph = build_transfer_graph()
    edges_df = _transfer_edges()
    g = nx.Graph()
    for _, row in edges_df.iterrows():
        g.add_edge(row["account_id"], row["counterparty_id"])
    components = [
        {
            "members": sorted(c),
            "size": len(c),
            "internal_total": round(
                float(
                    edges_df[
                        edges_df["account_id"].isin(c)
                        & edges_df["counterparty_id"].isin(c)
                    ]["total_amount"].sum()
                ),
                2,
            ),
        }
        for c in nx.connected_components(g)
    ]
    components.sort(key=lambda c: -c["internal_total"])
    return {
        "transfer_volume": graph["total_transfer_volume"],
        "accounts_in_network": graph["node_count"],
        "edge_count": graph["edge_count"],
        "components": components,
        "receiver_only": find_receiver_only_accounts()["accounts"],
        "layering_hops": detect_layering()["accounts"],
    }
