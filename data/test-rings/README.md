# Test rings — generalization datasets

Same-schema synthetic datasets that plant a **different** coordinated ring (or
none) to prove the investigator's detectors are adaptive — nothing baked in.

The **background mirrors the original `track02` dataset's aesthetic**: the same 9
ip-regions, the same right-skewed amount distribution (median ~$31), comparable
account ages, the same 90-day 2026 window, and — like the original — every
account-to-account transfer belongs to the ring. Only the **ring** varies:
structuring threshold, hour concentration, cohort tightness, flow topology, size.

Regenerate deterministically: `python3 data/generate_test_rings.py`
Registered in `backend/app/data/datasets.py` (selectable in the UI picker) with
answer keys for `backend/eval.py`.

| Dataset            | File                | Ring | Exposure      | What it stress-tests                                     |
| ------------------ | ------------------- | ---- | ------------- | -------------------------------------------------------- |
| Synthetic — Ring C | `ring_c_fanin.csv`  | 11   | $846,252.35   | ~$3k band · midday burst · fan-in collection hub         |
| Synthetic — Ring D | `ring_d_chain.csv`  | 9    | $2,839,208.26 | ~$10k band · night burst · 4-hop layering chain          |
| Synthetic — Ring E | `ring_e_hard.csv`   | 6    | $83,487.45    | ~$500 band · **no timing tell** · loose cohort (stealth) |
| Synthetic — Clean  | `clean_control.csv` | 0    | —             | control · no ring · false-positive guard                 |

## Validation (live deployment)

**Ring C** — uploaded + investigated on the deployment: all **11/11** planted
accounts recovered, exposure **$846,252.35 to the cent**, confidence 0.99 (the
engine also flagged one background account, `AC-1190`, so precision 11/12).

Rings D and E and the clean control are registered with answer keys but not
re-scored on this revision; run `cd backend && .venv/bin/python eval.py <id>` to
score any of them.
