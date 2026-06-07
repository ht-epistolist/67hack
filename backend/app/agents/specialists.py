"""The investigator agents. The unsupervised engine proposes a CANDIDATE cluster;
each specialist then *corroborates or refutes* it from one lens (which members does
my evidence actually support?), and an adversarial Skeptic argues the cluster is
innocent and prunes weak members. Every fallback is deterministic so the pipeline
runs with no LLM key.
"""
from __future__ import annotations

from app.agents.base import Agent
from app.data.loader import get_data
from app.tools import account_tools, amount_tools, temporal_tools


def build_case_brief() -> str:
    s = get_data().summary()
    return (
        f"Case: a transaction dataset spanning {s['window_days']} days, "
        f"{s['total_accounts_seen']} accounts and {s['transactions']:,} transactions. "
        "An unsupervised engine has surfaced a candidate cluster of accounts that may "
        "be a coordinated ring. Counterparties prefixed 'AC-' are bank accounts (peer "
        "transfers); 'MR-' are merchants."
    )


def _members(candidate: dict | None) -> list[str]:
    return list(candidate.get("members", [])) if candidate else []


def _cluster_a2a():
    df = get_data().df
    return df[df["is_a2a"]]


# --------------------------- corroborators --------------------------------- #
async def _network_fallback(agent: Agent, candidate: dict | None) -> dict:
    members = set(_members(candidate))
    a2a = _cluster_a2a()
    internal = a2a[a2a["account_id"].isin(members) & a2a["counterparty_id"].isin(members)]
    supported = sorted(set(internal["account_id"]) | set(internal["counterparty_id"]))
    return {
        "title": "Peer-transfer corroboration",
        "summary": (
            f"{len(supported)} of the {len(members)} candidate accounts are wired "
            f"together by {len(internal)} internal peer transfers — a genuine money-flow "
            f"sub-network: {', '.join(supported)}."
        ),
        "flagged_accounts": supported,
        "signal": "account_to_account_transfers",
        "confidence": 0.9,
        "evidence": {"internal_transfers": int(len(internal))},
    }


async def _mule_fallback(agent: Agent, candidate: dict | None) -> dict:
    members = set(_members(candidate))
    df = get_data().df
    originators = set(df["account_id"].unique())
    a2a = _cluster_a2a()
    internal = a2a[a2a["account_id"].isin(members) & a2a["counterparty_id"].isin(members)]
    senders = set(internal["account_id"])
    receivers = set(internal["counterparty_id"])
    mules = sorted(m for m in members if m not in originators)
    hops = sorted(senders & receivers)
    supported = sorted(set(mules) | set(hops))
    return {
        "title": "Mules & layering corroboration",
        "summary": (
            f"{len(mules)} candidate accounts only receive and never originate "
            f"(mules: {', '.join(mules) or 'none'}); {len(hops)} both receive and "
            f"re-send (layering hops: {', '.join(hops) or 'none'})."
        ),
        "flagged_accounts": supported,
        "signal": "mule",
        "confidence": 0.85,
        "evidence": {"mules": mules, "hops": hops},
    }


async def _temporal_fallback(agent: Agent, candidate: dict | None) -> dict:
    members = set(_members(candidate))
    sync = temporal_tools.synchronized_accounts(min_share=0.6, top_hours=2)
    flagged = sorted(a["account_id"] for a in sync["accounts"] if a["account_id"] in members)
    return {
        "title": "Timing corroboration",
        "summary": (
            f"{len(flagged)} of the candidates cram most activity into a couple of "
            f"hours (vs a population median top-2-hour share of "
            f"{sync['population_median_share']:.0%}) — coordinated timing: "
            f"{', '.join(flagged) or 'none'}."
        ),
        "flagged_accounts": flagged,
        "signal": "off_hours",
        "confidence": 0.6,
        "evidence": {"baseline": sync["population_median_share"]},
    }


async def _structuring_fallback(agent: Agent, candidate: dict | None) -> dict:
    members = set(_members(candidate))
    hug = amount_tools.threshold_hugging(min_in_band=5)
    hit = {a["account_id"]: a for a in hug["accounts"]}
    flagged = sorted(m for m in members if m in hit)
    bands = sorted({hit[m]["threshold"] for m in flagged})
    band_txt = ", ".join(f"${int(b):,}" for b in bands) or "a round threshold"
    return {
        "title": "Structuring corroboration",
        "summary": (
            f"{len(flagged)} candidates pin transfers just under a round ceiling they "
            f"never cross ({band_txt}) — deliberate structuring: {', '.join(flagged) or 'none'}."
        ),
        "flagged_accounts": flagged,
        "signal": "structuring",
        "confidence": 0.75,
        "evidence": {"thresholds": bands},
    }


async def _profiler_fallback(agent: Agent, candidate: dict | None) -> dict:
    members = set(_members(candidate))
    cohort = {a["account_id"] for a in account_tools.recent_cohort()["accounts"]}
    dev = account_tools.device_sharing()
    dev_members = set()
    for d in dev["devices"]:
        accs = set(d["accounts"]) & members
        if len(accs) > 1:
            dev_members |= accs
    flagged = sorted((cohort & members) | dev_members)
    return {
        "title": "Profile corroboration",
        "summary": (
            f"{len(cohort & members)} candidates belong to a freshly-opened cohort and "
            f"{len(dev_members)} share devices — synthetic/coordinated identities: "
            f"{', '.join(flagged) or 'none'}."
        ),
        "flagged_accounts": flagged,
        "signal": "new_account_cohort",
        "confidence": 0.7,
        "evidence": {"cohort_members": sorted(cohort & members)},
    }


# ----------------------------- skeptic ------------------------------------- #
async def _skeptic_fallback(agent: Agent, candidate: dict | None) -> dict:
    """Adversarial: which candidate members look like ordinary accounts that were
    swept in? Veto members with no money-flow tie, not in the cohort, and not a
    receiver-only mule (i.e. linked only incidentally)."""
    members = _members(candidate)
    df = get_data().df
    originators = set(df["account_id"].unique())
    a2a = _cluster_a2a()
    member_set = set(members)
    internal = a2a[a2a["account_id"].isin(member_set) & a2a["counterparty_id"].isin(member_set)]
    in_network = set(internal["account_id"]) | set(internal["counterparty_id"])
    cohort = {a["account_id"] for a in account_tools.recent_cohort()["accounts"]}

    vetoed = []
    for m in members:
        receiver_only = m not in originators
        if m in in_network or m in cohort or receiver_only:
            continue  # has a real tie — leave it
        vetoed.append(m)  # only incidentally linked; argue innocence
    return {
        "title": "Adversarial review",
        "summary": (
            f"Challenged all {len(members)} candidates for innocent explanations. "
            + (
                f"{len(vetoed)} look like ordinary accounts swept in by coincidence and "
                f"should be dropped: {', '.join(vetoed)}."
                if vetoed
                else "Every member has a concrete tie (peer transfers, shared cohort, or "
                "mule role) — the cluster holds up."
            )
        ),
        "flagged_accounts": vetoed,
        "signal": "skeptic_veto",
        "confidence": 0.8,
        "evidence": {"vetoed": vetoed},
    }


# --------------------------- agent specs ----------------------------------- #
def build_specialists() -> list[Agent]:
    return [
        Agent(
            key="network", name="Network Analyst", color="#6366f1",
            signal="account_to_account_transfers",
            role="Corroborates peer-transfer money flow",
            tools=["connected_component", "build_transfer_graph", "account_profile",
                   "compare_accounts", "account_neighborhood", "coordination_score"],
            recall_query="candidate cluster peer transfers money flow",
            fallback_fn=_network_fallback,
            system_prompt=(
                "You are the Network Analyst. Given a candidate cluster, confirm which "
                "members are genuinely connected by peer transfers (a money-flow "
                "sub-network) and which have no transfer tie. Use connected_component, "
                "account_neighborhood and coordination_score."
            ),
        ),
        Agent(
            key="mule_hunter", name="Mule Hunter", color="#ec4899",
            signal="mule",
            role="Confirms collection mules & layering hops",
            tools=["find_receiver_only_accounts", "detect_layering", "account_profile",
                   "account_neighborhood", "compare_accounts", "coordination_score"],
            recall_query="mules receive only layering hops candidate",
            fallback_fn=_mule_fallback,
            system_prompt=(
                "You are the Mule Hunter. Among the candidate members, identify which "
                "only ever receive peer transfers (collection mules) and which receive "
                "and re-send (layering hops). Use account_neighborhood to trace flows."
            ),
        ),
        Agent(
            key="temporal", name="Temporal Analyst", color="#f59e0b",
            signal="off_hours",
            role="Confirms synchronized timing",
            tools=["synchronized_accounts", "time_clustering", "hour_histogram",
                   "compare_accounts", "coordination_score"],
            recall_query="timing synchronized hours coordinated candidate",
            fallback_fn=_temporal_fallback,
            system_prompt=(
                "You are the Temporal Analyst. Determine which candidate members show "
                "abnormally concentrated, synchronized timing (scripted transfers) vs "
                "the population baseline. Prefer synchronized_accounts and time_clustering."
            ),
        ),
        Agent(
            key="structuring", name="Structuring Analyst", color="#10b981",
            signal="structuring",
            role="Confirms threshold-hugging amounts",
            tools=["threshold_hugging", "repeated_amounts", "amount_overview",
                   "compare_accounts", "coordination_score"],
            recall_query="amounts under threshold structuring repeated candidate",
            fallback_fn=_structuring_fallback,
            system_prompt=(
                "You are the Structuring Analyst. Determine which candidate members keep "
                "amounts just under a round threshold they never cross, or repeat a fixed "
                "amount. Use threshold_hugging and repeated_amounts."
            ),
        ),
        Agent(
            key="profiler", name="Account Profiler", color="#06b6d4",
            signal="new_account_cohort",
            role="Confirms cohort & shared infrastructure",
            tools=["recent_cohort", "device_sharing", "peer_comparison", "account_profile",
                   "compare_accounts", "shared_infrastructure"],
            recall_query="newly opened cohort shared devices synthetic candidate",
            fallback_fn=_profiler_fallback,
            system_prompt=(
                "You are the Account Profiler. Determine which candidate members belong "
                "to a freshly-opened cohort or share devices/IPs — synthetic or "
                "operator-controlled identities. Use recent_cohort, device_sharing and "
                "shared_infrastructure."
            ),
        ),
        Agent(
            key="skeptic", name="Adversarial Skeptic", color="#a855f7",
            signal="skeptic_veto",
            role="Argues the cluster is innocent; prunes weak members",
            tools=["account_profile", "peer_comparison", "compare_accounts",
                   "account_neighborhood", "shared_infrastructure", "coordination_score"],
            recall_query="legitimate explanation merchant customers innocent",
            fallback_fn=_skeptic_fallback,
            system_prompt=(
                "You are the Adversarial Skeptic. Your job is to DEFEND the candidate "
                "accounts: argue each could be innocent (a merchant and its customers, a "
                "shared household device, normal payroll timing). Flag any member that "
                "lacks a concrete collusion tie (peer transfers, shared cohort, or mule "
                "role) so it can be dropped. Be rigorous but fair — only flag the weakly "
                "linked, not the whole cluster."
            ),
        ),
    ]
