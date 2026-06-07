"""Benchmark the multi-agent system on a dataset.

Runs the full investigation (offline-safe) and, *if an answer key exists for that
dataset*, scores the verdict on precision / recall / exposure. With no key it just
reports the findings — so it works for uploaded/unknown datasets too.

    cd backend && .venv/bin/python eval.py            # default dataset (track02)
    cd backend && .venv/bin/python eval.py ring_b     # any registered dataset id
"""
from __future__ import annotations

import asyncio
import sys

from app.agents.orchestrator import run_investigation
from app.data import datasets


def _prf(found: set[str], truth: set[str]) -> tuple[float, float, float]:
    tp = len(found & truth)
    precision = tp / len(found) if found else 0.0
    recall = tp / len(truth) if truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


async def main() -> int:
    ds_id = sys.argv[1] if len(sys.argv) > 1 else "track02"
    if datasets.find(ds_id) is None:
        print(f"unknown dataset '{ds_id}'. Available: {[d['id'] for d in datasets.list_datasets()]}")
        return 2
    datasets.select(ds_id)
    key = datasets.answer_key()

    verdict = await run_investigation(fresh=True)
    found = set(verdict.get("ring", []))
    exposure = float(verdict.get("exposure", 0.0))

    print("\n" + "=" * 56)
    print(f" frtc — benchmark · {datasets.active()['name']}")
    print("=" * 56)
    print(f" flagged ring : {sorted(found)}")
    print(f" exposure     : ${exposure:,.2f}")
    print(f" confidence   : {verdict.get('confidence')}")

    if not key:
        print("-" * 56)
        print(" no answer key for this dataset — reporting findings only.")
        print("=" * 56)
        return 0

    truth = set(key["ring"])
    precision, recall, f1 = _prf(found, truth)
    print(f" expected     : {sorted(truth)}")
    print(f" missing      : {sorted(truth - found) or '—'}")
    print(f" extra        : {sorted(found - truth) or '—'}")
    print("-" * 56)
    print(f" precision    : {precision:.0%}    recall: {recall:.0%}    F1: {f1:.2f}")
    ok = found == truth
    if "exposure" in key:
        err = abs(exposure - key["exposure"])
        print(f" exposure err : ${err:,.2f}  (truth ${key['exposure']:,.2f})")
        ok = ok and err < 1.0
    print("=" * 56)
    print(" RESULT       :", "PASS ✅" if ok else "FAIL ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
