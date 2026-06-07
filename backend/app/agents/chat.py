"""Analyst chat — a grounded, tool-using assistant the analyst can cross-question
about the dataset, the flagged ring, and individual accounts.

It reuses the same OpenRouter tool-calling loop as the investigators, with the full
analytics + drill-down toolset plus a `recall_memory` tool over Cognee. Every answer
must be grounded in tool results / recalled findings — it is told to say "I don't
know" rather than invent account ids, amounts, or relationships.
"""
from __future__ import annotations

import json
from typing import AsyncIterator

from app import llm
from app.agents.base import _summarize
from app.data.loader import get_data
from app.events import bus
from app.memory.cognee_memory import memory
from app.tools.registry import call_tool, openai_tool_specs, tool_names

MAX_ITERS = 5

_RECALL_SPEC = {
    "type": "function",
    "function": {
        "name": "recall_memory",
        "description": "Semantically recall prior investigation findings written to "
        "Cognee shared memory (what the specialist agents concluded).",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}

_SYSTEM = (
    "You are a financial-crime analysis assistant for the active case. Answer the "
    "analyst's questions about the dataset, the flagged ring, and individual accounts.\n"
    "Rules:\n"
    "- Ground EVERY answer in tool results or recalled memory. Never invent account "
    "ids, amounts, dates, or relationships.\n"
    "- If the tools and memory don't support an answer, say you don't know.\n"
    "- Be concise (2–5 sentences); cite concrete account ids and numbers from the tools.\n"
    "- Counterparties prefixed AC- are bank accounts (peer transfers); MR- are merchants."
)


def _context() -> str:
    s = get_data().summary()
    lines = [
        f"Active dataset: {s['transactions']:,} transactions, "
        f"{s['total_accounts_seen']} accounts, {s['window_days']} days, "
        f"{s['a2a_transactions']} peer transfers."
    ]
    verdict = next((e for e in reversed(bus.history) if e["type"] == "verdict"), None)
    if verdict and verdict.get("ring"):
        lines.append(
            f"Latest verdict: a ring of {verdict['ring_size']} accounts "
            f"({', '.join(verdict['ring'])}); internal exposure "
            f"${float(verdict['exposure']):,.2f}."
        )
    else:
        lines.append(
            "No investigation has been run yet this session — use the tools to analyse "
            "the dataset directly."
        )
    return "\n".join(lines)


async def chat_stream(history: list[dict], question: str) -> AsyncIterator[dict]:
    """Yield events: {tool|tool_result|answer|error}."""
    if not llm.available():
        yield {
            "type": "answer",
            "text": "The analyst chat needs an LLM (set OPENROUTER_API_KEY). It's "
            "currently running in deterministic mode, so live Q&A is disabled.",
        }
        return

    tools = openai_tool_specs(tool_names()) + [_RECALL_SPEC]
    messages: list[dict] = [{"role": "system", "content": f"{_SYSTEM}\n\n{_context()}"}]
    for m in history[-8:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": str(m["content"])[:2000]})
    messages.append({"role": "user", "content": question})

    for _ in range(MAX_ITERS):
        try:
            msg = await llm.chat(messages, tools=tools, max_tokens=600)
        except Exception as e:
            yield {"type": "answer", "text": f"(LLM error: {e})"}
            return

        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            yield {"type": "answer", "text": msg.content or "(no answer)"}
            return

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [tc.model_dump() for tc in tool_calls],
            }
        )
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            yield {"type": "tool", "tool": name, "args": args}
            if name == "recall_memory":
                hits = await memory.recall(args.get("query", question), top_k=5)
                result = {
                    "findings": [
                        {"agent": h["agent"], "title": h["title"], "text": h["text"],
                         "accounts": h.get("accounts", [])}
                        for h in hits
                    ]
                }
            else:
                result = call_tool(name, args)
            yield {"type": "tool_result", "tool": name, "summary": _summarize(result)}
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)[:6000]}
            )

    # Out of tool iterations — force a grounded final answer.
    messages.append(
        {"role": "user", "content": "Give your final answer now, concise and grounded "
         "in the tool results above."}
    )
    try:
        msg = await llm.chat(messages, max_tokens=500)
        yield {"type": "answer", "text": msg.content or "(no answer)"}
    except Exception as e:
        yield {"type": "answer", "text": f"(LLM error: {e})"}
