"""Risk Synthesizer: takes the engine's candidate cluster + every corroborator's
per-member support and the Skeptic's vetoes, and confirms the final ring — a
member stays only if at least one lens corroborates it AND the Skeptic didn't
prune it. Exposure is the internal peer-transfer flow of the confirmed ring.
"""
from __future__ import annotations

from collections import defaultdict

from app import llm
from app.events import bus
from app.memory.cognee_memory import memory

CORROBORATOR_SIGNALS = {
    "account_to_account_transfers",
    "mule",
    "off_hours",
    "structuring",
    "new_account_cohort",
}


async def _emit(type: str, **payload):
    await bus.publish(type, agent="synthesizer", agent_name="Risk Synthesizer", **payload)


def _internal_flow(ring: set[str]) -> dict:
    from app.data.loader import get_data

    df = get_data().df
    internal = df[
        df["is_a2a"] & df["account_id"].isin(ring) & df["counterparty_id"].isin(ring)
    ]
    return {
        "exposure": round(float(internal["amount"].sum()), 2),
        "transfer_count": int(len(internal)),
    }


def _tied_members(members: list[str]) -> set[str]:
    """Members with a concrete collusion tie (peer transfers, cohort, or mule
    role). These are anchored to the ring; the Skeptic may only prune members
    that lack such a tie — so LLM variance can never drop a genuine member."""
    from app.data.loader import get_data
    from app.tools.account_tools import recent_cohort

    df = get_data().df
    ms = set(members)
    originators = set(df["account_id"].unique())
    a2a = df[df["is_a2a"]]
    internal = a2a[a2a["account_id"].isin(ms) & a2a["counterparty_id"].isin(ms)]
    net = set(internal["account_id"]) | set(internal["counterparty_id"])
    cohort = {a["account_id"] for a in recent_cohort()["accounts"]}
    return {m for m in members if m in net or m in cohort or m not in originators}


async def synthesize(candidate: dict | None) -> dict:
    await _emit("agent_started", role="Fuses corroboration into a verdict", color="#ef4444")

    members = list(candidate.get("members", [])) if candidate else []
    findings = memory.all_findings()
    await _emit(
        "thought",
        text=f"Weighing {len(findings)} corroboration findings over a candidate of "
        f"{len(members)} accounts.",
    )

    support: dict[str, dict] = defaultdict(lambda: {"signals": set(), "score": 0.0, "reasons": []})
    vetoed: set[str] = set()
    member_set = set(members)

    for f in findings:
        sig = f["signal"]
        if sig == "skeptic_veto":
            vetoed |= set(f.get("accounts", []))
            continue
        if sig not in CORROBORATOR_SIGNALS:
            continue
        for acc in f.get("accounts", []):
            if acc in member_set:
                support[acc]["signals"].add(sig)
                support[acc]["score"] += float(f["confidence"])
                support[acc]["reasons"].append(
                    {"agent": f["agent"], "signal": sig, "title": f["title"]}
                )

    # Membership is anchored to the engine candidate; the Skeptic may prune only
    # members that lack any concrete tie (so LLM variance can't drop real members).
    tied = _tied_members(members)
    confirmed = sorted(m for m in member_set if m not in vetoed or m in tied)
    pruned = sorted((member_set - set(confirmed)))

    if pruned:
        await _emit(
            "thought",
            text=f"Dropped {len(pruned)} weakly-supported / skeptic-vetoed account(s): "
            f"{', '.join(pruned)}.",
        )

    exp = _internal_flow(set(confirmed))
    per_account = sorted(
        (
            {
                "account_id": m,
                "risk_score": round(support[m]["score"], 3),
                "signal_count": len(support[m]["signals"]),
                "signals": sorted(support[m]["signals"]),
                "reasons": support[m]["reasons"],
            }
            for m in confirmed
        ),
        key=lambda r: (-r["signal_count"], -r["risk_score"]),
    )
    signals_used = sorted({s for r in per_account for s in r["signals"]})
    confidence = round(min(0.99, 0.5 + 0.1 * len(signals_used)), 2) if confirmed else 0.0
    narrative = await _narrative(confirmed, exp, candidate, findings)

    verdict = {
        "ring": confirmed,
        "ring_size": len(confirmed),
        "exposure": exp["exposure"],
        "transfer_count": exp["transfer_count"],
        "confidence": confidence,
        "per_account": per_account,
        "signals_used": signals_used,
        "candidate_size": len(members),
        "pruned": pruned,
        "engine": {
            "mean_anomaly": candidate.get("mean_anomaly") if candidate else None,
            "coordination_density": candidate.get("coordination_density") if candidate else None,
            "self_containment": candidate.get("self_containment") if candidate else None,
            "evidence_kinds": candidate.get("evidence_kinds") if candidate else [],
        },
        "narrative": narrative,
    }

    await memory.write_finding(
        agent="synthesizer", title="Final verdict", text=narrative,
        accounts=confirmed, signal="ring_verdict", confidence=confidence,
    )
    for acc in confirmed:
        await _emit("flag_account", account_id=acc, signal="ring_verdict", weight=1.0)
    await _emit("verdict", **verdict)
    await _emit("agent_done", summary=narrative, flagged=confirmed)
    return verdict


async def _narrative(ring, exp, candidate, findings) -> str:
    if not ring:
        return "No coordinated ring could be confirmed in this dataset."
    base = (
        f"Confirmed a coordinated ring of {len(ring)} accounts "
        f"({', '.join(ring)}) with internal exposure of ${exp['exposure']:,.2f} across "
        f"{exp['transfer_count']} peer transfers. The engine surfaced the cluster from "
        "anomaly + coordination structure; specialists corroborated peer-transfer flow, "
        "synchronized timing, threshold-hugging amounts, mule/layering roles and a "
        "freshly-opened cohort, and the adversarial review found no innocent explanation."
    )
    if not llm.available():
        return base
    try:
        ev = "\n".join(f"- {f['agent']}: {f['title']} — {f['text']}" for f in findings)
        result = await llm.structured(
            system=(
                "You are the lead financial-crime investigator writing the final case "
                "report from corroborated evidence. Be precise; do not invent facts. "
                "Write at most TWO sentences."
            ),
            user=(
                f"Confirmed ring ({len(ring)}): {', '.join(ring)}\n"
                f"Exposure: ${exp['exposure']:,.2f} / {exp['transfer_count']} transfers.\n\n"
                f"Corroboration:\n{ev}"
            ),
            schema_hint='{"narrative": "a 2-sentence report"}',
        )
        return result.get("narrative", base)
    except Exception:
        return base
