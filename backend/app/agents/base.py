"""Base investigator agent: an LLM tool-calling loop with a deterministic
fallback, wired to the event bus (for the live UI) and Cognee shared memory.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from app import llm
from app.events import bus
from app.memory.cognee_memory import memory
from app.tools.registry import call_tool, openai_tool_specs

# A fallback runs the agent's analysis deterministically (no LLM) over the
# candidate cluster and returns a conclusion dict:
# {title, summary, flagged_accounts, signal, confidence, evidence}.
FallbackFn = Callable[["Agent", "dict | None"], Awaitable[dict]]

MAX_TOOL_ITERS = 6


@dataclass
class Agent:
    key: str                # machine id, e.g. "network"
    name: str               # display name, e.g. "Network Analyst"
    color: str              # UI accent
    role: str               # one-line description for the roster
    system_prompt: str
    tools: list[str]
    fallback_fn: FallbackFn
    signal: str = ""        # canonical lens label (fixed, not LLM-chosen)
    recall_query: str = ""  # what to pull from shared memory before starting

    findings: list[dict] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    async def emit(self, type: str, **payload):
        await bus.publish(type, agent=self.key, agent_name=self.name, **payload)

    async def run(self, case_brief: str, candidate: dict | None = None) -> dict:
        await self.emit("agent_started", role=self.role, color=self.color)

        # 1. Pull peers' relevant findings from shared memory.
        recalled = []
        if self.recall_query:
            recalled = await memory.recall(self.recall_query, top_k=4)
            if recalled:
                await self.emit(
                    "memory_read",
                    query=self.recall_query,
                    hits=[
                        {"title": r["title"], "agent": r["agent"], "score": r.get("score")}
                        for r in recalled
                    ],
                )

        # 2. Investigate the candidate cluster.
        if llm.available():
            conclusion = await self._llm_investigate(case_brief, recalled, candidate)
        else:
            await self.emit(
                "thought",
                text="No LLM key configured — running my deterministic analysis path.",
            )
            conclusion = await self.fallback_fn(self, candidate)

        # 3. Persist conclusion to shared memory.
        flagged = conclusion.get("flagged_accounts", []) or []
        record = await memory.write_finding(
            agent=self.key,
            title=conclusion.get("title", self.name),
            text=conclusion.get("summary", ""),
            accounts=flagged,
            signal=self.signal or conclusion.get("signal", self.key),
            confidence=float(conclusion.get("confidence", 0.5)),
        )
        self.findings.append(record)
        await self.emit(
            "finding",
            title=record["title"],
            text=record["text"],
            accounts=flagged,
            signal=record["signal"],
            confidence=record["confidence"],
        )
        # 4. Light up the graph.
        for acc in flagged:
            await self.emit(
                "flag_account",
                account_id=acc,
                signal=conclusion.get("signal", self.key),
                weight=float(conclusion.get("confidence", 0.5)),
            )
        await self.emit(
            "agent_done", summary=conclusion.get("summary", ""), flagged=flagged
        )
        return conclusion

    # ------------------------------------------------------------------ #
    async def _llm_investigate(
        self, case_brief: str, recalled: list[dict], candidate: dict | None
    ) -> dict:
        mem_block = ""
        if recalled:
            mem_block = "\n\nRelevant findings already in shared memory:\n" + "\n".join(
                f"- ({r['agent']}) {r['title']}: {r['text']}" for r in recalled
            )
        cand_block = ""
        if candidate:
            cand_block = (
                f"\n\nThe detection engine flagged a CANDIDATE cluster of "
                f"{len(candidate['members'])} accounts to scrutinise:\n"
                f"{', '.join(candidate['members'])}\n"
                f"(engine evidence: {candidate.get('evidence_kinds')}, "
                f"anomaly {candidate.get('mean_anomaly')}, "
                f"self-containment {candidate.get('self_containment')}).\n"
                "Examine these accounts with your tools. State which members your "
                "lens genuinely supports as ring members and which look innocent."
            )
        messages = [
            {
                "role": "system",
                "content": self.system_prompt
                + " Be terse: every message is a short note or headline, never a "
                "paragraph. No preamble, no restating the task.",
            },
            {
                "role": "user",
                "content": (
                    f"{case_brief}{cand_block}{mem_block}\n\nUse your tools to "
                    "investigate, then stop. State your conclusion in ONE short "
                    "sentence (≤25 words) naming the account IDs your lens supports."
                ),
            },
        ]
        tool_specs = openai_tool_specs(self.tools)

        for _ in range(MAX_TOOL_ITERS):
            try:
                msg = await llm.chat(messages, tools=tool_specs)
            except Exception as e:
                await self.emit("thought", text=f"(LLM error, falling back: {e})")
                return await self.fallback_fn(self, candidate)

            if msg.content:
                await self.emit("thought", text=msg.content)

            tool_calls = getattr(msg, "tool_calls", None)
            if not tool_calls:
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [tc.model_dump() for tc in tool_calls],
                }
            )
            for tc in tool_calls:
                fn = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                await self.emit("tool_call", tool=fn, args=args)
                result = call_tool(fn, args)
                await self.emit("tool_result", tool=fn, summary=_summarize(result))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result)[:6000],
                    }
                )

        # Force a structured conclusion from the reasoning so far.
        return await self._conclude(messages, candidate)

    async def _conclude(self, messages: list[dict], candidate: dict | None) -> dict:
        transcript = "\n".join(
            m.get("content", "") for m in messages if m.get("role") in ("assistant", "tool")
        )[:8000]
        try:
            return await llm.structured(
                system=(
                    f"You are {self.name}. Summarize YOUR investigation into a JSON "
                    "verdict. Only flag accounts your evidence actually supports. "
                    "Keep `summary` to ONE short sentence (≤25 words)."
                ),
                user=f"Investigation notes:\n{transcript}",
                schema_hint=(
                    '{"title": "≤6 words", "summary": "one short sentence", '
                    '"flagged_accounts": ["AC-XXXX", ...], '
                    '"signal": str, "confidence": 0.0-1.0}'
                ),
            )
        except Exception:
            return await self.fallback_fn(self, candidate)


def _summarize(result) -> str:
    """Compact a tool result for the live feed (full payload goes to the LLM)."""
    if isinstance(result, dict):
        if "error" in result:
            return f"error: {result['error']}"
        bits = []
        for k in ("flagged_count", "receiver_only_count", "cohort_size",
                  "shared_device_count", "accounts_in_network", "transfer_volume",
                  "member_count", "intermediary_count", "internal_transfer_total"):
            if k in result:
                bits.append(f"{k}={result[k]}")
        if "accounts" in result and isinstance(result["accounts"], list):
            ids = [a.get("account_id") for a in result["accounts"][:8] if isinstance(a, dict)]
            if ids:
                bits.append("accounts=" + ",".join(filter(None, ids)))
        return "; ".join(bits) or "ok"
    return str(result)[:200]
