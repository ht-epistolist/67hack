# Test rings — generalization datasets

Same-schema synthetic datasets that plant a **different** coordinated ring (or
none) to prove the investigator's detectors are adaptive — nothing baked in.
Each varies every axis the engine keys on: structuring threshold, hour
concentration, cohort tightness, flow topology, and ring size.

Regenerate deterministically: `python3 data/generate_test_rings.py`
Registered in `backend/app/data/datasets.py` (selectable in the UI picker) with
answer keys for `backend/eval.py`.

| Dataset | File                | Ring | Exposure      | What it stress-tests                                     |
| ------- | ------------------- | ---- | ------------- | -------------------------------------------------------- |
| Ring C  | `ring_c_fanin.csv`  | 11   | $839,715.93   | ~$3k band · midday burst · fan-in collection hub         |
| Ring D  | `ring_d_chain.csv`  | 9    | $2,838,524.29 | ~$10k band · weekend/night · 4-hop layering chain        |
| Ring E  | `ring_e_hard.csv`   | 6    | $83,483.68    | ~$500 band · **no timing tell** · loose cohort (stealth) |
| Clean   | `clean_control.csv` | 0    | —             | control · no ring · false-positive guard                 |

## Validation (live deployment)

Uploaded + investigated on the deployed app:

- **Ring C** → recovered all 11 accounts, exposure to the cent, confidence 0.99 — **100% precision/recall**.
- **Ring E** (hard) → recovered all 6 accounts despite no timing signal and a loose cohort, confidence 0.99 — **100% precision/recall**.

Ring D and the clean control are registered but not yet live-scored.
