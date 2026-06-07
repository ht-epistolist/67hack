"""Tool registry: maps tool names to their implementation + an OpenAI-style
JSON schema, provides a dispatcher, and declares which tools each specialist
agent is allowed to use.
"""
from __future__ import annotations

from typing import Any, Callable

from app.tools import (
    account_tools,
    amount_tools,
    graph_tools,
    investigate_tools,
    temporal_tools,
)

# name -> (callable, json-schema-parameters, one-line description)
_TOOLS: dict[str, tuple[Callable, dict, str]] = {
    # ---- graph / network ----
    "transfer_network_overview": (
        graph_tools.transfer_network_overview,
        {"type": "object", "properties": {}},
        "Summary of the whole account-to-account transfer network: clusters, "
        "volume, receiver-only mules and layering hops.",
    ),
    "build_transfer_graph": (
        graph_tools.build_transfer_graph,
        {
            "type": "object",
            "properties": {
                "min_txns": {
                    "type": "integer",
                    "description": "Only include edges with >= this many transfers.",
                }
            },
        },
        "The directed account-to-account transfer graph (nodes + weighted edges).",
    ),
    "find_receiver_only_accounts": (
        graph_tools.find_receiver_only_accounts,
        {"type": "object", "properties": {}},
        "Accounts that only ever receive peer transfers and never originate "
        "activity (mule signature).",
    ),
    "detect_layering": (
        graph_tools.detect_layering,
        {"type": "object", "properties": {}},
        "Accounts that both receive and re-send transfers (layering hops).",
    ),
    "connected_component": (
        graph_tools.connected_component,
        {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "e.g. AC-0009"}
            },
            "required": ["account_id"],
        },
        "The cluster of accounts connected to a given account via transfers, "
        "plus the internal transfer total (exposure).",
    ),
    # ---- temporal ----
    "hour_histogram": (
        temporal_tools.hour_histogram,
        {
            "type": "object",
            "properties": {
                "account_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional subset of accounts; omit for all.",
                }
            },
        },
        "Distribution of transactions across the 24 hours of the day.",
    ),
    "off_hours_accounts": (
        temporal_tools.off_hours_accounts,
        {
            "type": "object",
            "properties": {
                "start_hour": {"type": "integer"},
                "end_hour": {"type": "integer"},
                "min_ratio": {"type": "number"},
            },
        },
        "Accounts whose activity is concentrated in a quiet night window.",
    ),
    "synchronized_accounts": (
        temporal_tools.synchronized_accounts,
        {
            "type": "object",
            "properties": {
                "min_share": {"type": "number"},
                "top_hours": {"type": "integer"},
                "min_txns": {"type": "integer"},
            },
        },
        "Accounts whose activity is abnormally concentrated in a few hours "
        "(scripted/coordinated timing), relative to the population baseline.",
    ),
    "time_clustering": (
        temporal_tools.time_clustering,
        {
            "type": "object",
            "properties": {
                "account_ids": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["account_ids"],
        },
        "How tightly a set of accounts cluster in time (synchronized timing).",
    ),
    # ---- amounts ----
    "amount_overview": (
        amount_tools.amount_overview,
        {
            "type": "object",
            "properties": {
                "account_ids": {"type": "array", "items": {"type": "string"}}
            },
        },
        "Percentile summary of transaction amounts for a scope.",
    ),
    "threshold_hugging": (
        amount_tools.threshold_hugging,
        {
            "type": "object",
            "properties": {
                "min_in_band": {"type": "integer"},
                "band_ratio": {
                    "type": "number",
                    "description": "Lower band edge as a fraction of the threshold (default 0.5).",
                },
            },
        },
        "Adaptively finds accounts that keep many transactions just under a round "
        "alert threshold they never cross (structuring) — threshold detected per "
        "account, not assumed.",
    ),
    "repeated_amounts": (
        amount_tools.repeated_amounts,
        {
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"],
        },
        "Clusters of near-identical repeated amounts for one account.",
    ),
    # ---- accounts ----
    "account_profile": (
        account_tools.account_profile,
        {
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"],
        },
        "Full behavioural profile for one account (works for mules too).",
    ),
    "recent_cohort": (
        account_tools.recent_cohort,
        {
            "type": "object",
            "properties": {"window_days": {"type": "integer"}},
        },
        "Accounts opened shortly before the observation window starts.",
    ),
    "device_sharing": (
        account_tools.device_sharing,
        {"type": "object", "properties": {}},
        "Devices used by more than one account.",
    ),
    "peer_comparison": (
        account_tools.peer_comparison,
        {
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"],
        },
        "Compare one account's metrics to population baselines (z-scores).",
    ),
    # ---- drill-down / hypothesis-testing ----
    "candidate_overview": (
        investigate_tools.candidate_overview,
        {"type": "object", "properties": {}},
        "The unsupervised engine's candidate ring(s): members, anomaly, "
        "coordination density, self-containment and evidence kinds.",
    ),
    "compare_accounts": (
        investigate_tools.compare_accounts,
        {
            "type": "object",
            "properties": {"account_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["account_ids"],
        },
        "Side-by-side behavioural profiles of a set of accounts (spot the shared pattern).",
    ),
    "account_neighborhood": (
        investigate_tools.account_neighborhood,
        {
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"],
        },
        "An account's transfer counterparties (both directions) and device-mates.",
    ),
    "shared_infrastructure": (
        investigate_tools.shared_infrastructure,
        {
            "type": "object",
            "properties": {"account_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["account_ids"],
        },
        "Devices / IP regions shared across a set of accounts (collusion evidence).",
    ),
    "coordination_score": (
        investigate_tools.coordination_score,
        {
            "type": "object",
            "properties": {"account_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["account_ids"],
        },
        "Score how coordinated an arbitrary set of accounts is — test a hypothesis.",
    ),
}

# Drill-down tools every corroborator/skeptic shares.
_DRILL = ["compare_accounts", "account_neighborhood", "shared_infrastructure", "coordination_score"]

# Which tools each agent is allowed to call. Specialists now *examine a candidate
# cluster* the engine proposed, so they get their lens tools + drill-down freedom.
AGENT_TOOLSETS: dict[str, list[str]] = {
    "network": ["connected_component", "build_transfer_graph", "account_profile", *_DRILL],
    "mule_hunter": ["find_receiver_only_accounts", "detect_layering", "account_profile", *_DRILL],
    "temporal": ["synchronized_accounts", "time_clustering", "hour_histogram", *_DRILL],
    "structuring": ["threshold_hugging", "repeated_amounts", "amount_overview", *_DRILL],
    "profiler": ["recent_cohort", "device_sharing", "peer_comparison", "account_profile", *_DRILL],
    # The skeptic argues for innocence — it needs to inspect, compare and test.
    "skeptic": ["account_profile", "peer_comparison", "candidate_overview", *_DRILL],
    "synthesizer": list(_TOOLS.keys()),
    "orchestrator": ["candidate_overview"],
}


def openai_tool_specs(names: list[str]) -> list[dict]:
    """Return OpenAI tool-calling specs for the given tool names."""
    specs = []
    for name in names:
        _, params, desc = _TOOLS[name]
        specs.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": params,
                },
            }
        )
    return specs


def call_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Dispatch a tool call by name with keyword arguments."""
    if name not in _TOOLS:
        return {"error": f"unknown tool '{name}'"}
    fn, _, _ = _TOOLS[name]
    try:
        return fn(**(arguments or {}))
    except TypeError as e:
        return {"error": f"bad arguments for {name}: {e}"}
    except Exception as e:  # never let a tool crash the agent loop
        return {"error": f"{name} failed: {e}"}


def tool_names() -> list[str]:
    return list(_TOOLS.keys())
