"""Generate several same-schema test datasets for the frtc fraud investigator.

Each dataset plants a DIFFERENT ring (or none), varying every axis the adaptive
detectors key on — structuring threshold, hour concentration, cohort tightness,
flow topology, ring size — so they prove "nothing is baked in." Schema + AC-/MR-
conventions match backend/app/data/loader.py exactly, so each CSV is selectable
(drop into data/) or uploadable via the UI.

Run:  python3 data/generate_test_rings.py
Writes data/test-rings/*.csv (deterministic; seeded) and prints answer keys +
a paste-ready datasets.py registry snippet.
"""
from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "test-rings"
REGIONS = ["NY", "NJ", "CT", "PA", "MA", "FL", "GA", "IL", "TX", "CA"]
FOREIGN = ["JP", "DE", "SG", "FR", "UK"]
CATS = ["grocery", "retail", "electronics", "dining", "fuel", "services", "travel"]


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


def _background(rng, rows, n_normal, n_txn, window_start, window_end, hours=(6, 23)):
    """Realistic merchant-spend background + a little innocent a2a noise."""
    normals = [f"AC-{i:04d}" for i in range(1000, 1000 + n_normal)]
    opens = {a: datetime(2022, 6, 1) + timedelta(days=rng.randint(0, 1000)) for a in normals}
    devs = {a: f"DV-{rng.randint(10000, 99999)}" for a in normals}
    regions = {a: rng.choice(REGIONS) for a in normals}
    span = int((window_end - window_start).total_seconds())
    for _ in range(n_txn):
        a = rng.choice(normals)
        # ~3% innocent peer transfers so a2a alone isn't a giveaway
        if rng.random() < 0.03:
            cp = rng.choice(normals)
            amt = round(abs(rng.gauss(180, 160)) + 5, 2)
        else:
            cp = f"MR-{rng.randint(1, 240):04d}"
            amt = round(abs(rng.gauss(70, 60)) + 2, 2)
            if rng.random() < 0.02:
                amt = round(rng.uniform(2000, 14000), 2)  # legit large purchases
        ts = window_start + timedelta(seconds=rng.randint(0, span))
        ts = ts.replace(hour=int(min(hours[1], max(hours[0], rng.gauss(14, 4)))),
                        minute=rng.randint(0, 59), second=rng.randint(0, 59))
        region = regions[a] if rng.random() > 0.02 else rng.choice(FOREIGN)
        rows.append(_row(a, cp, amt, ts, rng.choice(CATS), devs[a], region, opens[a]))
    return normals


def _plant(rng, rows, ring, flow, window_start, band, hours, cohort_days, n_per_edge,
           covers=()):
    """Plant a ring: fresh cohort, structuring band, hour concentration, flow edges."""
    members = list(ring) + list(covers)
    opens = {a: window_start - timedelta(days=rng.randint(*cohort_days)) for a in members}
    devs = {a: f"DV-{rng.randint(10000, 99999)}" for a in members}
    regions = {a: rng.choice(REGIONS) for a in members}
    span = int((window_start + timedelta(days=80) - window_start).total_seconds())

    def ts_for():
        t = window_start + timedelta(seconds=rng.randint(0, span))
        if hours is not None:
            t = t.replace(hour=rng.choice(hours))
        return t.replace(minute=rng.randint(0, 59), second=rng.randint(0, 59))

    exposure = 0.0
    for src, dst in flow:
        for _ in range(n_per_edge):
            amt = rng.uniform(*band)
            exposure += amt
            rows.append(_row(src, dst, amt, ts_for(), "services",
                             devs[src], regions[src], opens[src]))
    # cover accounts: cohort members with only innocent daytime merchant spend
    for c in covers:
        for _ in range(rng.randint(8, 14)):
            t = (window_start + timedelta(days=rng.randint(0, 70))).replace(
                hour=rng.randint(9, 18), minute=rng.randint(0, 59))
            rows.append(_row(c, f"MR-{rng.randint(1,240):04d}",
                             round(abs(rng.gauss(60, 40)) + 5, 2), t,
                             rng.choice(CATS), devs[c], regions[c], opens[c]))
    return round(exposure, 2)


# --------------------------------------------------------------------------- #
def ring_c(seed=11):
    """Fan-in collection hub · ~$3k band · midday (11-13h) · 11 accounts · FL/GA."""
    rng = random.Random(seed)
    ws, we = datetime(2026, 2, 1), datetime(2026, 5, 1)
    rows: list[dict] = []
    _background(rng, rows, 280, 4400, ws, we)
    senders = ["AC-0601", "AC-0602", "AC-0603", "AC-0604", "AC-0605"]
    hub = "AC-0600"
    sinks = ["AC-0606", "AC-0607", "AC-0608"]
    covers = ["AC-0609", "AC-0610"]
    ring = sorted(senders + [hub] + sinks + covers)
    flow = [(s, hub) for s in senders] + [(hub, k) for k in sinks]
    exp = _plant(rng, rows, senders + [hub] + sinks, flow, ws,
                 band=(2550, 2985), hours=(11, 12, 13), cohort_days=(10, 18),
                 n_per_edge=38, covers=covers)
    _writer(rows, OUT_DIR / "ring_c_fanin.csv")
    return {"id": "ring_c", "name": "Test — Ring C (fan-in hub)", "file": "ring_c_fanin.csv",
            "ring": ring, "exposure": exp, "rows": len(rows),
            "note": "$3k structuring, midday burst, fan-in collection hub"}


def ring_d(seed=23):
    """Deep layering chain · ~$10k band · weekend 03h · 9 accounts · high exposure."""
    rng = random.Random(seed)
    ws, we = datetime(2025, 11, 1), datetime(2026, 1, 30)
    rows: list[dict] = []
    _background(rng, rows, 300, 4600, ws, we)
    chain = ["AC-0700", "AC-0701", "AC-0702", "AC-0703", "AC-0704"]  # 4-hop chain to sink
    feeder = "AC-0705"
    sinks = ["AC-0706", "AC-0707"]
    cover = ["AC-0708"]
    ring = sorted(chain + [feeder] + sinks + cover)
    flow = [(chain[i], chain[i + 1]) for i in range(len(chain) - 1)]
    flow += [(feeder, chain[1]), (chain[3], sinks[0]), (chain[2], sinks[1])]
    exp = _plant(rng, rows, chain + [feeder] + sinks, flow, ws,
                 band=(9350, 9960), hours=(2, 3, 4), cohort_days=(4, 9),
                 n_per_edge=42, covers=cover)
    _writer(rows, OUT_DIR / "ring_d_chain.csv")
    return {"id": "ring_d", "name": "Test — Ring D (deep chain)", "file": "ring_d_chain.csv",
            "ring": ring, "exposure": exp, "rows": len(rows),
            "note": "$10k structuring, weekend/night, 4-hop layering chain, ~$2M exposure"}


def ring_e(seed=37):
    """HARD: round-$500 · NO hour concentration · loose cohort · star · 6 accounts."""
    rng = random.Random(seed)
    ws, we = datetime(2026, 3, 1), datetime(2026, 5, 30)
    rows: list[dict] = []
    _background(rng, rows, 260, 4200, ws, we)
    senders = ["AC-0801", "AC-0802", "AC-0803"]
    hub = "AC-0800"
    sink = "AC-0804"
    cover = ["AC-0805"]
    ring = sorted(senders + [hub, sink] + cover)
    flow = [(s, hub) for s in senders] + [(hub, sink)]
    exp = _plant(rng, rows, senders + [hub, sink], flow, ws,
                 band=(452, 498), hours=None, cohort_days=(2, 40),
                 n_per_edge=44, covers=cover)
    _writer(rows, OUT_DIR / "ring_e_hard.csv")
    return {"id": "ring_e", "name": "Test — Ring E (hard / stealthy)", "file": "ring_e_hard.csv",
            "ring": ring, "exposure": exp, "rows": len(rows),
            "note": "$500 structuring, NO timing tell, loose cohort — stress test"}


def clean_control(seed=51):
    """No planted ring — only background (incl. innocent a2a). Verdict should be 'no ring'."""
    rng = random.Random(seed)
    ws, we = datetime(2026, 1, 1), datetime(2026, 4, 1)
    rows: list[dict] = []
    _background(rng, rows, 300, 5000, ws, we)
    _writer(rows, OUT_DIR / "clean_control.csv")
    return {"id": "clean", "name": "Test — Clean (no ring)", "file": "clean_control.csv",
            "ring": [], "exposure": 0.0, "rows": len(rows),
            "note": "control — no coordinated ring; checks the false-positive guard"}


if __name__ == "__main__":
    results = [ring_c(), ring_d(), ring_e(), clean_control()]
    print(f"\nwrote {len(results)} datasets -> {OUT_DIR}\n")
    for r in results:
        print(f"  {r['file']:22}  {r['rows']:5} rows  ring={len(r['ring']):2}  "
              f"exposure=${r['exposure']:>12,.2f}   {r['note']}")
        if r["ring"]:
            print(f"      ring: {r['ring']}")
    print("\n--- paste-ready datasets.py answer keys ---")
    for r in results:
        if r["ring"]:
            print(f'    {{"id": "{r["id"]}", "name": "{r["name"]}", '
                  f'"path": str(REPO_ROOT / "data" / "test-rings" / "{r["file"]}"), '
                  f'"answer_key": {{"ring": {r["ring"]}, "exposure": {r["exposure"]}}}}},')
        else:
            print(f'    {{"id": "{r["id"]}", "name": "{r["name"]}", '
                  f'"path": str(REPO_ROOT / "data" / "test-rings" / "{r["file"]}"), '
                  f'"answer_key": {{"ring": []}}}},')
