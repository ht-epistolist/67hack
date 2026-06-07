"""Cognee-backed shared memory for the investigator agents.

Design notes
------------
* The **transaction knowledge graph** (Account nodes + transferred_to edges) and
  every agent **Finding** are stored as typed `DataPoint`s via `add_data_points`,
  which writes to Cognee's local Kuzu graph + LanceDB vector store using
  **fastembed** embeddings. This path needs *no* LLM, so memory works offline and
  doesn't burn OpenRouter tokens on every run.
* Cross-agent **recall** is real semantic search over Cognee's vector store
  (`vector_engine.search`), which returns ranked node ids; we resolve the content
  from an id-keyed mirror kept at write time (fast, and survives if a later Cognee
  call hiccups).
* If Cognee fails to initialise for any reason, the layer transparently degrades
  to an in-process store so the multi-agent demo never hard-crashes. `degraded`
  exposes which mode is active.

All configuration is set BEFORE cognee is imported/initialised.
"""
from __future__ import annotations

import os
import shutil
from typing import Any

from pydantic import SkipValidation

from app.config import settings
from app.data.loader import get_data

# --- configure cognee via env BEFORE importing it -------------------------- #
os.environ.setdefault("COGNEE_SKIP_CONNECTION_TEST", "true")
# Quieter logs for the demo.
os.environ.setdefault("LITELLM_LOG", "ERROR")

_COGNEE_OK = False
try:
    import cognee
    from cognee.low_level import DataPoint, setup as cognee_setup
    from cognee.infrastructure.engine.models.Edge import Edge
    from cognee.tasks.storage import add_data_points
    from cognee.infrastructure.databases.vector import get_vector_engine
    from cognee.infrastructure.databases.graph import get_graph_engine

    _COGNEE_OK = True
except Exception as _e:  # pragma: no cover - import guard
    cognee = None
    _IMPORT_ERR = _e


# ----------------------------- typed nodes --------------------------------- #
if _COGNEE_OK:

    class Account(DataPoint):
        name: str
        profile: str  # natural-language profile (embedded for recall)
        opened: str = ""
        receiver_only: bool = False
        sends_to: SkipValidation[Any] = None
        metadata: dict = {"index_fields": ["profile"]}

    class Finding(DataPoint):
        text: str  # the embedded, recallable statement
        agent: str
        title: str
        accounts: str  # comma-joined account ids
        signal: str
        confidence: float
        metadata: dict = {"index_fields": ["text"]}


class CogneeMemory:
    """Shared investigation memory (graph + semantic recall)."""

    def __init__(self) -> None:
        self.degraded = not (_COGNEE_OK and settings.use_cognee)
        self._findings: list[dict] = []
        self._finding_by_id: dict[str, dict] = {}
        self._initialised = False
        self._cognee_started = False

    # --------------------------------------------------------------------- #
    def _configure(self) -> None:
        cognee.config.system_root_directory(str(settings.cognee_dir / "system"))
        cognee.config.data_root_directory(str(settings.cognee_dir / "data"))
        # Local embeddings (no key, fully offline).
        cognee.config.set_embedding_provider("fastembed")
        cognee.config.set_embedding_model(settings.embedding_model)
        cognee.config.set_embedding_dimensions(settings.embedding_dimensions)
        # LLM via OpenRouter — only used by optional GRAPH_COMPLETION narration.
        cognee.config.set_llm_provider("custom")
        cognee.config.set_llm_model(settings.cognee_llm_model)
        cognee.config.set_llm_endpoint(settings.openrouter_base_url)
        cognee.config.set_llm_api_key(settings.openrouter_api_key or "no-key")

    async def init(self, fresh: bool = True) -> None:
        """Configure + create the local databases. Safe to call once per run."""
        if fresh:
            # Drop the in-process mirror so findings never leak across runs/datasets.
            self._findings.clear()
            self._finding_by_id.clear()
        # Retry Cognee every run (don't stay degraded after a transient failure).
        if not (_COGNEE_OK and settings.use_cognee):
            self.degraded = True
            self._initialised = True
            return
        self.degraded = False
        try:
            self._configure()
            if fresh:
                if self._cognee_started:
                    # Same process: let Cognee release/recreate its own stores.
                    await cognee.prune.prune_data()
                    await cognee.prune.prune_system(metadata=True)
                else:
                    # First init: wipe any stale Kuzu/LanceDB lock left on disk by
                    # an ungracefully-killed process (the usual cause of a silent
                    # degrade to in-process).
                    shutil.rmtree(settings.cognee_dir, ignore_errors=True)
            await cognee_setup()
            self._cognee_started = True
            self._initialised = True
        except Exception as e:  # fall back, keep running
            self.degraded = True
            self._initialised = True
            print(f"[memory] Cognee init failed, using in-process memory: {e!r}")

    # --------------------------------------------------------------------- #
    async def ingest_transaction_graph(self) -> dict:
        """Build the Account/transfer knowledge graph in Cognee (offline)."""
        data = get_data()
        # Aggregate a2a transfers per directed pair.
        a2a = data.df[data.df["is_a2a"]]
        pair = (
            a2a.groupby(["account_id", "counterparty_id"])["amount"]
            .agg(["size", "sum"])
            .reset_index()
        )
        node_ids = set(pair["account_id"]) | set(pair["counterparty_id"])
        originators = set(data.df["account_id"].unique())

        if self.degraded:
            return {"nodes": len(node_ids), "edges": int(len(pair)), "backend": "in-process"}

        try:
            # Build Account nodes.
            accounts: dict[str, Any] = {}
            for acc in sorted(node_ids):
                od = data.open_date(acc)
                receiver_only = acc not in originators
                profile = (
                    f"Account {acc}; "
                    f"opened {od.date().isoformat() if od is not None else 'unknown'}; "
                    f"{'receiver-only (no originated activity)' if receiver_only else 'active sender'}."
                )
                accounts[acc] = Account(
                    name=acc,
                    profile=profile,
                    opened=od.date().isoformat() if od is not None else "",
                    receiver_only=receiver_only,
                )
            # Attach transfer edges.
            cap = settings.cognee_max_edges or len(pair)
            for src, grp in pair.groupby("account_id"):
                edges = []
                for _, row in grp.iterrows():
                    edges.append(
                        (
                            Edge(
                                weight=round(float(row["sum"]), 2),
                                relationship_type="transferred_to",
                            ),
                            accounts[row["counterparty_id"]],
                        )
                    )
                accounts[src].sends_to = edges
            await add_data_points(list(accounts.values()))
            return {"nodes": len(accounts), "edges": int(len(pair)), "backend": "cognee"}
        except Exception as e:
            self.degraded = True
            print(f"[memory] graph ingest failed, degrading: {e!r}")
            return {"nodes": len(node_ids), "edges": int(len(pair)), "backend": "in-process"}

    # --------------------------------------------------------------------- #
    async def write_finding(
        self,
        agent: str,
        title: str,
        text: str,
        accounts: list[str],
        signal: str,
        confidence: float,
    ) -> dict:
        """Persist an agent finding to shared memory (+ in-process mirror)."""
        record = {
            "agent": agent,
            "title": title,
            "text": text,
            "accounts": accounts,
            "signal": signal,
            "confidence": round(float(confidence), 3),
        }
        if not self.degraded:
            try:
                node = Finding(
                    text=text,
                    agent=agent,
                    title=title,
                    accounts=",".join(accounts),
                    signal=signal,
                    confidence=float(confidence),
                )
                await add_data_points([node])
                record["id"] = str(node.id)
            except Exception as e:
                self.degraded = True
                print(f"[memory] write_finding degraded: {e!r}")
        record.setdefault("id", f"f{len(self._findings)}")
        self._findings.append(record)
        self._finding_by_id[record["id"]] = record
        return record

    async def recall(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic recall of prior findings from shared memory."""
        if not self.degraded:
            try:
                ve = get_vector_engine()
                hits = await ve.search("Finding_text", query_text=query, limit=top_k)
                out = []
                for h in hits:
                    rec = self._finding_by_id.get(str(h.id))
                    if rec:
                        out.append({**rec, "score": round(float(h.score), 3)})
                if out:
                    return out
            except Exception as e:
                print(f"[memory] recall fell back to keyword match: {e!r}")
        # Degraded / empty: keyword overlap ranking over the mirror.
        q = set(query.lower().split())
        ranked = sorted(
            self._findings,
            key=lambda r: -len(q & set((r["text"] + " " + r["title"]).lower().split())),
        )
        return ranked[:top_k]

    def all_findings(self) -> list[dict]:
        """Every finding written this run (structured, for the synthesizer)."""
        return list(self._findings)

    async def graph_snapshot(self) -> dict:
        """Nodes + edges currently in the Cognee graph (for inspection/viz)."""
        if self.degraded:
            return {"nodes": [], "edges": [], "backend": "in-process"}
        try:
            ge = await get_graph_engine()
            nodes, edges = await ge.get_graph_data()
            return {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "backend": "cognee",
            }
        except Exception as e:
            return {"nodes": [], "edges": [], "error": repr(e)}


# Process-wide singleton.
memory = CogneeMemory()
