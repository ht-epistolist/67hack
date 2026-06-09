"""Generate several test datasets for the frtc fraud investigator.

The BACKGROUND mirrors the original Track 02 dataset's "aesthetic" exactly — same
9 ip-regions, same right-skewed amount distribution (median ~$31), same account
age range, same 90-day 2026 window, and (like the original) every account-to-
account transfer belongs to the ring. Only the RING varies — threshold band, hour
concentration, cohort tightness, flow topology, size — so the datasets look like
the same bank's data with a different ring planted, and prove the detectors adapt.

Run:  python3 data/generate_test_rings.py
Writes data/test-rings/*.csv (deterministic; seeded) and prints answer keys.
"""
from __future__ import annotations

import csv
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "test-rings"

# Match track02 exactly: 6 US regions + 3 foreign (rare).
REGIONS = ["CA", "CT", "FL", "NJ", "NY", "PA"]
FOREIGN = ["FR", "JP", "UK"]
CATS = ["dining", "electronics", "fuel", "grocery", "retail", "services", "travel"]

# Same 90-day window as the original (2026-03-03 → 2026-06-01) for every dataset.
WINDOW_START = datetime(2026, 3, 3)
WINDOW_END = datetime(2026, 6, 1)
_SPAN = int((WINDOW_END - WINDOW_START).total_seconds())

# Amount model tuned to the original: median ~$31, mean ~$92, rare large purchases.
_AMT_MU = math.log(31.0)   # lognormal median = e^mu = 31
_AMT_SIGMA = 1.25


def _writer(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(99)
    rng.shuffle(rows)
    for i, r in enumerate(rows, 1):
        r["txn_id"] = f"TX-{i:05d}"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "txn_id", "account_id", "counterparty_id", "amount", "timestamp",
            "merchant_category", "device_id", "ip_region", "account_open_date",
        ])
        w.writeheader()
        w.writerows(rows)


def _row(acc, cp, amount, ts, cat, dev, region, opened) -> dict:
    return {
        "txn_id": "",
        "account_id": acc,
        "counterparty_id": cp,
        "amount": round(amount, 2),
        "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "merchant_category": cat,
        "device_id": dev,
        "ip_region": region,
        "account_open_date": opened.strftime("%Y-%m-%d"),
    }


def _ts(rng: random.Random, hours=None) -> datetime:
    t = WINDOW_START + timedelta(seconds=rng.randint(0, _SPAN))
    hour = rng.choice(hours) if hours is not None else int(min(23, max(0, rng.gauss(14, 5))))
    return t.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))


def _amount(rng: random.Random) -> float:
    if rng.random() < 0.016:                       # rare large legit purchases (→ max ~$15k)
        return round(rng.uniform(2000, 15000), 2)
    return round(max(1.3, rng.lognormvariate(_AMT_MU, _AMT_SIGMA)), 2)


def _background(rng, rows, n_normal=290, n_txn=4750):
    """Merchant-spend background only — like track02, NO innocent a2a (every a2a is the ring)."""
    normals = [f"AC-{i:04d}" for i in range(1000, 1000 + n_normal)]
    # opens ~1 year before the window (original example: 2025-02-14)
    opens = {a: datetime(2024, 6, 1) + timedelta(days=rng.randint(0, 560)) for a in normals}
    devs = {a: f"DV-{rng.randint(10000, 99999)}" for a in normals}
    regions = {a: rng.choice(REGIONS) for a in normals}
    for _ in range(n_txn):
        a = rng.choice(normals)
        cp = f"MR-{rng.randint(1, 240):04d}"
        region = regions[a] if rng.random() > 0.004 else rng.choice(FOREIGN)
        rows.append(_row(a, cp, _amount(rng), _ts(rng), rng.choice(CATS),
                         devs[a], region, opens[a]))
    return normals


def _plant(rng, rows, ring, flow, band, hours, cohort_days, n_per_edge, covers=()):
    """Plant a ring: fresh coordinated cohort, structuring band, hour concentration, flow edges."""
    members = list(ring) + list(covers)
    opens = {a: WINDOW_START - timedelta(days=rng.randint(*cohort_days)) for a in members}
    devs = {a: f"DV-{rng.randint(10000, 99999)}" for a in members}
    regions = {a: rng.choice(REGIONS) for a in members}
    exposure = 0.0
    for src, dst in flow:
        for _ in range(n_per_edge):
            amt = rng.uniform(*band)
            exposure += amt
            rows.append(_row(src, dst, amt, _ts(rng, hours), "services",
                             devs[src], regions[src], opens[src]))
    for c in covers:                                # cohort members with only innocent merchant spend
        for _ in range(rng.randint(8, 14)):
            rows.append(_row(c, f"MR-{rng.randint(1,240):04d}", _amount(rng),
                             _ts(rng), rng.choice(CATS), devs[c], regions[c], opens[c]))
    return round(exposure, 2)


# --------------------------------------------------------------------------- #
def ring_c(seed=11):
    """Fan-in collection hub · ~$3k band · midday (11-13h) · 11 accounts."""
    rng = random.Random(seed)
    rows: list[dict] = []
    _background(rng, rows)
    senders = ["AC-0601", "AC-0602", "AC-0603", "AC-0604", "AC-0605"]
    hub, sinks, covers = "AC-0600", ["AC-0606", "AC-0607", "AC-0608"], ["AC-0609", "AC-0610"]
    ring = sorted(senders + [hub] + sinks + covers)
    flow = [(s, hub) for s in senders] + [(hub, k) for k in sinks]
    exp = _plant(rng, rows, senders + [hub] + sinks, flow, band=(2550, 2985),
                 hours=(11, 12, 13), cohort_days=(14, 24), n_per_edge=38, covers=covers)
    _writer(rows, OUT_DIR / "ring_c_fanin.csv")
    return {"id": "ring_c", "name": "Synthetic — Ring C", "file": "ring_c_fanin.csv",
            "ring": ring, "exposure": exp, "rows": len(rows),
            "note": "$3k structuring, midday burst, fan-in collection hub"}


def ring_d(seed=23):
    """Deep layering chain · ~$10k band · night (2-4h) · 9 accounts · high exposure."""
    rng = random.Random(seed)
    rows: list[dict] = []
    _background(rng, rows)
    chain = ["AC-0700", "AC-0701", "AC-0702", "AC-0703", "AC-0704"]
    feeder, sinks, cover = "AC-0705", ["AC-0706", "AC-0707"], ["AC-0708"]
    ring = sorted(chain + [feeder] + sinks + cover)
    flow = [(chain[i], chain[i + 1]) for i in range(len(chain) - 1)]
    flow += [(feeder, chain[1]), (chain[3], sinks[0]), (chain[2], sinks[1])]
    exp = _plant(rng, rows, chain + [feeder] + sinks, flow, band=(9350, 9960),
                 hours=(2, 3, 4), cohort_days=(4, 9), n_per_edge=42, covers=cover)
    _writer(rows, OUT_DIR / "ring_d_chain.csv")
    return {"id": "ring_d", "name": "Synthetic — Ring D", "file": "ring_d_chain.csv",
            "ring": ring, "exposure": exp, "rows": len(rows),
            "note": "$10k structuring, night burst, 4-hop layering chain"}


def ring_e(seed=37):
    """HARD: round-$500 · NO hour concentration · loose cohort · star · 6 accounts."""
    rng = random.Random(seed)
    rows: list[dict] = []
    _background(rng, rows)
    senders, hub, sink, cover = ["AC-0801", "AC-0802", "AC-0803"], "AC-0800", "AC-0804", ["AC-0805"]
    ring = sorted(senders + [hub, sink] + cover)
    flow = [(s, hub) for s in senders] + [(hub, sink)]
    exp = _plant(rng, rows, senders + [hub, sink], flow, band=(452, 498),
                 hours=None, cohort_days=(2, 40), n_per_edge=44, covers=cover)
    _writer(rows, OUT_DIR / "ring_e_hard.csv")
    return {"id": "ring_e", "name": "Synthetic — Ring E", "file": "ring_e_hard.csv",
            "ring": ring, "exposure": exp, "rows": len(rows),
            "note": "$500 structuring, NO timing tell, loose cohort — stress test"}


def clean_control(seed=51):
    """No planted ring — background only (no a2a). Verdict should be 'no ring'."""
    rng = random.Random(seed)
    rows: list[dict] = []
    _background(rng, rows, n_txn=5000)
    _writer(rows, OUT_DIR / "clean_control.csv")
    return {"id": "clean", "name": "Synthetic — Clean (control)", "file": "clean_control.csv",
            "ring": [], "exposure": 0.0, "rows": len(rows),
            "note": "control — no coordinated ring; checks the false-positive guard"}


if __name__ == "__main__":
    results = [ring_c(), ring_d(), ring_e(), clean_control()]
    print(f"\nwrote {len(results)} datasets -> {OUT_DIR}\n")
    for r in results:
        print(f"  {r['file']:22}  {r['rows']:5} rows  ring={len(r['ring']):2}  "
              f"exposure=${r['exposure']:>13,.2f}   {r['note']}")
