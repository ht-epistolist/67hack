"""Lead Investigator / Orchestrator: sets up shared memory, dispatches the
specialist agents concurrently, then runs the synthesizer. This is the single
entry point the API and CLI call to run an investigation.
"""
from __future__ import annotations

import asyncio

from app import llm
from app.agents.specialists import build_case_brief, build_specialists
from app.agents.synthesizer import synthesize
from app.data.loader import get_data
from app.events import bus
from app.memory.cognee_memory import memory

_running = asyncio.Lock()


async def _emit(type: str, **payload):
    await bus.publish(type, agent="orchestrator", agent_name="Lead Investigator", **payload)


async def run_investigation(fresh: bool = True) -> dict:
    """Run the full multi-agent investigation, streaming events to the bus."""
    if _running.locked():
        await _emit("status", phase="busy", message="An investigation is already running.")
        return {}

    async with _running:
        bus.reset()
        data = get_data()
        await _emit(
            "status",
            phase="start",
            message="Opening case file for Crestline Community Bank.",
            data_summary=data.summary(),
            llm_enabled=llm.available(),
        )

        # 1. Shared memory online.
        await _emit("status", phase="memory", message="Initialising Cognee shared memory…")
        await memory.init(fresh=fresh)
        await _emit(
            "ml_step",
            model="fastembed · all-MiniLM-L6-v2 (384-dim)",
            message="Embedding accounts + transfers with fastembed (all-MiniLM-L6-v2, "
            "384-dim) into Cognee's vector + graph store…",
        )
        g = await memory.ingest_transaction_graph()
        await _emit(
            "status",
            phase="memory_ready",
            message=(
                f"Knowledge graph built in Cognee "
                f"({g.get('nodes')} accounts, {g.get('edges')} transfer edges, "
                f"backend={g.get('backend')})."
            ),
            graph_nodes=g.get("nodes"),
            graph_edges=g.get("edges"),
            backend=g.get("backend"),
        )

        # 2. Unsupervised engine surfaces candidate ring(s) — no prior knowledge.
        await _emit(
            "status",
            phase="engine",
            message="Running the unsupervised detector (preprocessing stage)…",
        )
        from app.engine import detector

        result = detector.run()
        for s in result.get("steps", []):
            await _emit("ml_step", stage=s["stage"], message=s["message"])
            await asyncio.sleep(0.45)
        candidates = result["candidates"]
        if not candidates:
            await _emit(
                "status",
                phase="no_ring",
                message="No coordinated cluster stood out from the population.",
            )
            verdict = await synthesize(None)
            await _emit("status", phase="done", message="Investigation complete.")
            return verdict

        candidate = candidates[0]
        await _emit(
            "candidate",
            members=candidate["members"],
            mean_anomaly=candidate["mean_anomaly"],
            coordination_density=candidate["coordination_density"],
            self_containment=candidate["self_containment"],
            evidence_kinds=candidate["evidence_kinds"],
            message=(
                f"Engine flagged a candidate cluster of {candidate['size']} accounts "
                f"(anomaly {candidate['mean_anomaly']}, self-containment "
                f"{candidate['self_containment']}). Dispatching agents to corroborate."
            ),
        )
        for acc in candidate["members"]:
            await _emit("flag_account", account_id=acc, signal="candidate", weight=0.4)

        # 3. Specialists corroborate / refute the candidate concurrently.
        specialists = build_specialists()
        await _emit(
            "plan",
            message="Dispatching specialists to corroborate or refute the candidate.",
            agents=[
                {"key": a.key, "name": a.name, "role": a.role, "color": a.color}
                for a in specialists
            ],
        )
        case_brief = build_case_brief()
        await asyncio.gather(*(a.run(case_brief, candidate) for a in specialists))

        # 4. Synthesize the corroborated verdict.
        await _emit(
            "status",
            phase="synthesis",
            message="Corroboration in. Confirming the ring…",
        )
        verdict = await synthesize(candidate)

        await _emit("status", phase="done", message="Investigation complete.")
        return verdict
