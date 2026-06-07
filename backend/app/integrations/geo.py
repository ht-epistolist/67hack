"""Geo (geodo.ai) outreach integration.

Used as a *post-investigation action*: email the assembled SAR to a recipient
(a compliance officer, the analyst's own inbox) through the user's Geo-connected
Gmail. Geo's MCP endpoint is plain HTTP JSON-RPC, so we call it directly with
httpx — no MCP client needed.

Send is a confirmation-gated ("write") tool: the first call can return a
``confirmation_token`` that must be replayed to actually execute. The user
clicking "Email SAR" in the UI is that confirmation, so we replay it once.

The token lives only in the backend (``GEO_API_TOKEN`` env / App Platform
secret) — never the frontend, never the repo.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import httpx

from app.config import settings

GEO_URL = "https://app.geodo.ai/api/mcp"


class GeoError(RuntimeError):
    """Geo is unreachable, returned an error, or is not configured."""


def geo_enabled() -> bool:
    return bool(settings.geo_api_token)


def _parse(raw: str) -> dict:
    """Geo replies as JSON or as a streamable-HTTP SSE stream; handle both."""
    raw = raw.strip()
    if not raw.startswith("{"):
        datas = [ln[5:].strip() for ln in raw.splitlines() if ln.startswith("data:")]
        raw = datas[-1] if datas else raw
    return json.loads(raw)


async def _rpc(method: str, params: dict) -> dict:
    if not geo_enabled():
        raise GeoError("GEO_API_TOKEN is not configured")
    headers = {
        "Authorization": f"Bearer {settings.geo_api_token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(GEO_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = _parse(resp.text)
    except httpx.HTTPError as exc:
        raise GeoError(f"Geo request failed: {exc}") from exc
    if "error" in data:
        raise GeoError(str(data["error"]))
    return data.get("result", {})


def _unwrap(result: dict) -> Any:
    """Geo tool results carry a JSON document in ``content[0].text`` — unwrap it."""
    content = result.get("content")
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                try:
                    return json.loads(part["text"])
                except (ValueError, KeyError):
                    return part.get("text")
    return result


async def call_tool(name: str, arguments: dict | None = None) -> Any:
    return _unwrap(await _rpc("tools/call", {"name": name, "arguments": arguments or {}}))


async def account_state() -> Any:
    return await call_tool("geo_get_account_state")


def _find_confirmation_token(obj: Any) -> str | None:
    """Recursively locate a confirmation_token a gated tool handed back."""
    if isinstance(obj, dict):
        tok = obj.get("confirmation_token")
        if isinstance(tok, str) and tok:
            return tok
        for value in obj.values():
            tok = _find_confirmation_token(value)
            if tok:
                return tok
    elif isinstance(obj, list):
        for value in obj:
            tok = _find_confirmation_token(value)
            if tok:
                return tok
    return None


async def send_gmail(to: str, subject: str, body: str) -> Any:
    """Send a one-off Gmail via Geo, replaying the confirmation gate once."""
    args: dict[str, Any] = {
        "channel": "gmail",
        "to": to,
        "subject": subject,
        "body": body,
        "idempotency_key": uuid.uuid4().hex,
    }
    first = await call_tool("geo_send_manual_message", args)
    token = _find_confirmation_token(first)
    if token:
        args["confirmation_token"] = token
        return await call_tool("geo_send_manual_message", args)
    return first


# ── SAR → email formatting ────────────────────────────────────────────────── #

def _money(n: float) -> str:
    return f"${n:,.2f}"


def _num(n: int) -> str:
    return f"{n:,}"


def sar_email(sar: dict, examiner: str = "") -> tuple[str, str]:
    """Render the SAR dict (from app.sar.build_sar) into an email subject + body."""
    if sar.get("status") != "ready":
        raise GeoError("No completed investigation to report yet.")
    s = sar["summary"]
    subject = (
        f"{sar['report_id']} — Suspicious Activity Report "
        f"({s['ring_size']} accounts, {_money(s['exposure'])} exposure)"
    )
    lines = [
        f"SUSPICIOUS ACTIVITY REPORT — {sar['report_id']}",
        f"Institution: {sar['institution']['name']}",
        f"Filed: {sar['filed_on']}    "
        f"Period: {sar['period']['start']} → {sar['period']['end']} ({sar['period']['days']} days)",
        "",
        "SUMMARY",
        f"  Ring size:           {s['ring_size']} accounts",
        f"  Estimated exposure:  {_money(s['exposure'])}",
        f"  Internal transfers:  {s['transfer_count']}",
        f"  Confidence:          {s['confidence_tier']} ({s['confidence'] * 100:.0f}%)",
        f"  Reviewed:            {_num(s['transactions_reviewed'])} transactions / "
        f"{_num(s['accounts_reviewed'])} accounts",
        "",
        "NARRATIVE",
        (sar.get("narrative") or "").strip() or "  (none)",
        "",
        "SUBJECT ACCOUNTS",
    ]
    for sub in sar.get("subjects", []):
        lines.append(
            f"  • {sub['account_id']} — risk {sub['risk_score']}, "
            f"{sub['signal_count']} signal(s) — {sub['recommended_action']}"
        )
    findings = sar.get("findings", [])
    if findings:
        lines += ["", "KEY FINDINGS"]
        for f in findings[:8]:
            lines.append(
                f"  [{f['id']}] {f['title']} "
                f"({f['signal_label']}, confidence {f['confidence']})"
            )
    if examiner.strip():
        lines += ["", f"Prepared for review by: {examiner.strip()}"]
    lines += [
        "",
        "— Generated by the multi-agent fraud investigator and sent via Geo.",
    ]
    return subject, "\n".join(lines)
