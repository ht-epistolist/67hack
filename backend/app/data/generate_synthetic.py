"""Generate a second, same-schema dataset with a DIFFERENT planted ring, so the
dataset picker is meaningful and the system's generalization is demonstrable.

The ring here differs from Track 02 on every axis the detectors key on:
  - different account ids (AC-05xx) and a smaller ring (7 accounts)
  - structuring amount pinned just under $5,000 (vs ~$1,000)
  - activity concentrated at 22:00-23:00 (vs 02:00-04:00)
  - a freshly-opened cohort just before a different observation window

Run:  python -m app.data.generate_synthetic
Writes data/synthetic_ring_b.csv (deterministic; seeded).
"""
from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[3] / "data" / "synthetic_ring_b.csv"

REGIONS = ["TX", "WA", "OR", "AZ", "CO", "NV"]
FOREIGN = ["JP", "DE", "SG"]
CATS = ["grocery", "retail", "electronics", "dining", "fuel", "services", "travel"]
WINDOW_START = datetime(2026, 1, 5, 0, 0, 0)
WINDOW_END = datetime(2026, 4, 5, 0, 0, 0)


def _rand_ts(rng: random.Random, lo=WINDOW_START, hi=WINDOW_END) -> datetime:
    span = int((hi - lo).total_seconds())
    return lo + timedelta(seconds=rng.randint(0, span))


def generate(seed: int = 7) -> dict:
    rng = random.Random(seed)
    rows: list[dict] = []
    tx = 0

    def add(acc, cp, amount, ts, cat, dev, region, opened):
        nonlocal tx
        tx += 1
        rows.append(
            {
                "txn_id": f"TX-{tx:05d}",
                "account_id": acc,
                "counterparty_id": cp,
                "amount": round(amount, 2),
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "merchant_category": cat,
                "device_id": dev,
                "ip_region": region,
                "account_open_date": opened.strftime("%Y-%m-%d"),
            }
        )

    # ---- normal background population ----
    n_normal = 270
    normals = [f"AC-{i:04d}" for i in range(1000, 1000 + n_normal)]
    normal_open = {
        a: datetime(2023, 1, 1) + timedelta(days=rng.randint(0, 730)) for a in normals
    }
    normal_dev = {a: f"DV-{rng.randint(10000, 99999)}" for a in normals}
    normal_region = {a: rng.choice(REGIONS) for a in normals}
    for _ in range(4300):
        a = rng.choice(normals)
        cp = f"MR-{rng.randint(1, 240):04d}"
        # mostly small daytime purchases; a few foreign / large
        amt = round(abs(rng.gauss(70, 60)) + 2, 2)
        if rng.random() < 0.02:
            amt = round(rng.uniform(2000, 14000), 2)
        hour = int(min(23, max(6, rng.gauss(14, 4))))
        ts = _rand_ts(rng).replace(hour=hour, minute=rng.randint(0, 59))
        region = normal_region[a] if rng.random() > 0.02 else rng.choice(FOREIGN)
        add(a, cp, amt, ts, rng.choice(CATS), normal_dev[a], region, normal_open[a])

    # ---- the ring (7 accounts, AC-05xx) ----
    senders = ["AC-0500", "AC-0501", "AC-0502"]
    mules = ["AC-0503", "AC-0504"]          # receiver-only
    hop = "AC-0505"                          # receives and re-sends
    cover = "AC-0506"                        # cohort member, normal-looking traffic
    ring = senders + mules + [hop, cover]
    # tight, freshly-opened cohort just before the window
    ring_open = {
        a: WINDOW_START - timedelta(days=rng.randint(8, 26)) for a in ring
    }
    ring_dev = {a: f"DV-{rng.randint(10000, 99999)}" for a in ring}
    ring_region = {a: rng.choice(REGIONS) for a in ring}

    def ring_ts() -> datetime:
        # concentrated at 22:00-23:00
        ts = _rand_ts(rng)
        return ts.replace(hour=rng.choice([22, 23]), minute=rng.randint(0, 59))

    # money flow: senders -> mules/hop, hop -> a mule (layering), ~ $4,800 band
    flow = [
        ("AC-0500", "AC-0503"),
        ("AC-0501", "AC-0504"),
        ("AC-0502", "AC-0505"),
        ("AC-0505", "AC-0503"),  # layering hop forwards
    ]
    for src, dst in flow:
        for _ in range(40):
            amt = rng.uniform(4200, 4960)  # pinned just under $5,000
            add(src, dst, amt, ring_ts(), "services", ring_dev[src], ring_region[src], ring_open[src])

    # cover account: only normal daytime traffic (camouflage)
    for _ in range(11):
        amt = round(abs(rng.gauss(60, 40)) + 5, 2)
        ts = _rand_ts(rng).replace(hour=rng.randint(9, 18))
        add(cover, f"MR-{rng.randint(1,240):04d}", amt, ts, rng.choice(CATS),
            ring_dev[cover], ring_region[cover], ring_open[cover])

    rng.shuffle(rows)
    # renumber txn ids after shuffle for cleanliness
    for i, r in enumerate(rows, 1):
        r["txn_id"] = f"TX-{i:05d}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    exposure = sum(
        r["amount"] for r in rows
        if r["account_id"] in ring and r["counterparty_id"] in ring
    )
    return {
        "path": str(OUT),
        "rows": len(rows),
        "ring": sorted(ring),
        "exposure": round(exposure, 2),
    }


if __name__ == "__main__":
    info = generate()
    print(f"wrote {info['rows']} rows -> {info['path']}")
    print(f"planted ring ({len(info['ring'])}): {info['ring']}")
    print(f"internal exposure: ${info['exposure']:,.2f}")
