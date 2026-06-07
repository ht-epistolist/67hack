"""Assembles a Suspicious Activity Report (SAR) — the case's document of record.

Machines do the forensics, a human signs the document. This module turns the
investigation's verdict + every corroborated finding into a structured SAR:
subject accounts, a plain-English narrative, the evidence findings (each with a
citation id like ``F-07``), a method-reliability table, and a transaction-level
appendix backing the exposure figure. The frontend renders it as a paper-white
sheet and exports it to HTML / print.

All inputs come from the event history (the verdict + ``finding`` events) and the
active dataset, so the SAR is reproducible from whatever the last run streamed.
"""
from __future__ import annotations

import hashlib

from app.data import datasets
from app.data.loader import get_data
from app.events import bus

# Plain-English labels for each lens (no jargon reaches the document of record).
SIGNAL_LABEL: dict[str, str] = {
    "account_to_account_transfers": "Peer-to-peer transfers",
    "mule": "Mule / layering role",
    "off_hours": "Synchronized off-hours activity",
    "structuring": "Amounts under the reporting threshold",
    "new_account_cohort": "Freshly-opened account cohort",
    "skeptic_veto": "Adversarial challenge",
    "ring_verdict": "Confirmed ring",
    "candidate": "Engine candidate",
}

# The lenses that *corroborate* a ring member (everything except the adversarial
# challenge and the engine/verdict bookkeeping signals).
CORROBORATOR_SIGNALS = {
    "account_to_account_transfers",
    "mule",
    "off_hours",
    "structuring",
    "new_account_cohort",
}

APPENDIX_LIMIT = 60


def _confidence_tier(conf: float) -> str:
    if conf >= 0.8:
        return "High"
    if conf >= 0.6:
        return "Medium"
    if conf > 0:
        return "Low"
    return "None"


def _latest_verdict() -> dict | None:
    for evt in reversed(bus.history):
        if evt.get("type") == "verdict":
            return evt
    return None


def _finding_events() -> list[dict]:
    return [evt for evt in bus.history if evt.get("type") == "finding"]


def _report_id(dataset_id: str, ring: list[str], end_year: int) -> str:
    """Deterministic case number, e.g. ``SAR-2026-4417`` — stable per run/dataset."""
    seed = f"{dataset_id}|{'|'.join(ring)}".encode()
    digits = int(hashlib.md5(seed).hexdigest(), 16) % 10000
    return f"SAR-{end_year}-{digits:04d}"


def build_sar(appendix_limit: int = APPENDIX_LIMIT) -> dict:
    """Assemble the SAR for the most recent investigation, or a not-ready status."""
    verdict = _latest_verdict()
    if not verdict:
        return {"status": "no_investigation_yet"}

    ring: list[str] = list(verdict.get("ring", []))
    data = get_data()
    summary = data.summary()
    ds = datasets.active() or {}
    originators = set(data.df["account_id"].unique())
    ring_set = set(ring)

    # --- Evidence findings → citation ids ---------------------------------- #
    findings: list[dict] = []
    citations_by_account: dict[str, list[str]] = {}
    fid = 0
    for evt in _finding_events():
        sig = evt.get("signal")
        if sig == "ring_verdict":  # the synthesizer's own summary; not cited evidence
            continue
        fid += 1
        cid = f"F-{fid:02d}"
        accounts = list(evt.get("accounts", []) or [])
        rec = {
            "id": cid,
            "agent": evt.get("agent_name") or evt.get("agent") or "Investigator",
            "title": evt.get("title") or "Finding",
            "text": evt.get("text") or "",
            "signal": sig,
            "signal_label": SIGNAL_LABEL.get(sig, sig or "finding"),
            "confidence": round(float(evt.get("confidence", 0.0)), 2),
            "accounts": accounts,
            "adversarial": sig == "skeptic_veto",
        }
        findings.append(rec)
        for acc in accounts:
            citations_by_account.setdefault(acc, []).append(cid)

    # --- Subjects (confirmed ring members) --------------------------------- #
    per = {p["account_id"]: p for p in verdict.get("per_account", [])}
    subjects: list[dict] = []
    for acc in ring:
        p = per.get(acc, {})
        od = data.open_date(acc)
        signal_count = int(p.get("signal_count", 0))
        subjects.append(
            {
                "account_id": acc,
                "risk_score": round(float(p.get("risk_score", 0.0)), 2),
                "signal_count": signal_count,
                "signals": [SIGNAL_LABEL.get(s, s) for s in p.get("signals", [])],
                "opened": od.date().isoformat() if od is not None else None,
                "receiver_only": acc not in originators,
                "recommended_action": "Freeze & file" if signal_count >= 2 else "Enhanced monitoring",
                "citations": citations_by_account.get(acc, []),
            }
        )

    # --- Method-reliability table (the corroboration that held) ------------ #
    by_signal: dict[str, dict] = {}
    for f in findings:
        s = f["signal"]
        if s not in CORROBORATOR_SIGNALS:
            continue
        slot = by_signal.setdefault(s, {"findings": 0, "accounts": set()})
        slot["findings"] += 1
        slot["accounts"].update(a for a in f["accounts"] if a in ring_set)
    methods = [
        {
            "signal": s,
            "label": SIGNAL_LABEL.get(s, s),
            "findings": slot["findings"],
            "ring_accounts": len(slot["accounts"]),
        }
        for s, slot in sorted(by_signal.items(), key=lambda kv: -len(kv[1]["accounts"]))
    ]

    # --- Transaction appendix: the ring's internal flow (backs exposure) --- #
    df = data.df
    internal = df[
        df["is_a2a"] & df["account_id"].isin(ring_set) & df["counterparty_id"].isin(ring_set)
    ].sort_values("amount", ascending=False)
    appendix_rows = [
        [
            r["txn_id"],
            r["account_id"],
            r["counterparty_id"],
            round(float(r["amount"]), 2),
            r["timestamp"].strftime("%Y-%m-%d %H:%M"),
        ]
        for _, r in internal.head(appendix_limit).iterrows()
    ]

    # --- Grounding summary (claims checked vs. resolved) ------------------- #
    corroborating = [f for f in findings if not f["adversarial"]]
    resolved = sum(1 for f in corroborating if ring_set & set(f["accounts"]))

    confidence = float(verdict.get("confidence", 0.0))
    end_ts = data.window_end

    return {
        "status": "ready",
        "report_id": _report_id(ds.get("id", "dataset"), ring, end_ts.year),
        "filed_on": end_ts.date().isoformat(),
        "institution": {
            "name": ds.get("name") or "Reporting Institution",
            "dataset_id": ds.get("id"),
        },
        "period": {
            "start": summary["window_start"],
            "end": summary["window_end"],
            "days": summary["window_days"],
        },
        "summary": {
            "ring_size": verdict.get("ring_size", len(ring)),
            "exposure": verdict.get("exposure", 0.0),
            "transfer_count": verdict.get("transfer_count", 0),
            "confidence": round(confidence, 2),
            "confidence_tier": _confidence_tier(confidence),
            "transactions_reviewed": summary["transactions"],
            "accounts_reviewed": summary["total_accounts_seen"],
            "candidate_size": verdict.get("candidate_size"),
            "pruned": verdict.get("pruned", []),
        },
        "narrative": verdict.get("narrative", ""),
        "subjects": subjects,
        "findings": findings,
        "methods": methods,
        "grounding": {"claims": len(corroborating), "resolved": resolved},
        "engine": verdict.get("engine"),
        "appendix": {
            "columns": ["Transaction", "From", "To", "Amount", "Timestamp"],
            "rows": appendix_rows,
            "total_internal_transfers": int(len(internal)),
            "shown": len(appendix_rows),
        },
    }
