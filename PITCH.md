# Fraud Watch — Elevator Pitch

> Four AI agents turn 5,000 raw bank transactions into one ranked, pre-justified fraud case — for the analyst who has three minutes.

**Live demo → https://fraudwatch-one.vercel.app**

---

## The 30-second pitch

A community-bank fraud analyst gets three minutes per case. Their rules fire on
single transactions, so they're staring at thousands of disconnected rows and
never see the _shape_ between them — and the smartest fraud rings are built to
stay invisible: every transfer parked just under the $1,000 review trigger,
money fanned out across mule accounts, never a clean round-trip to flag.

**Fraud Watch runs four agents that collaborate through a shared memory graph.**
One _finds_ the suspicious transactions, one _ranks_ the accounts worst-first,
one _acts_ — escalate, freeze, or monitor — and one _writes_ the signable SAR
memo. Each agent hands off through memory, not glue code, and every decision
logs the exact rule that fired.

From one real Kaggle dataset, it re-derived **$161,750 in exposure across 250
sub-threshold transfers moved by 10 coordinated accounts** — matching the hidden
answer key to the cent, nothing hardcoded.

So instead of _discovering_ the ring from raw rows, the analyst _confirms_ it in
three minutes: money-path graph, a per-account "why flagged" table, and a
downloadable memo. **We don't replace the analyst's judgment. We give them back
their three minutes.**

## The one-liner

> Rules tell you a transaction is weird. Fraud Watch tells you it's a ring —
> and hands you the case file to prove it.

## The 15-second version

Fraud analysts get three minutes per case and only see one transaction at a
time, so coordinated rings hiding under the review threshold slip through.
Fraud Watch's four agents find, rank, action, and document the whole ring from
the raw data — turning a three-minute discovery into a three-minute
confirmation.

## How the pipeline works (50 words)

Four agents collaborate through a shared Cognee memory graph. FraudFinder runs
deterministic detectors (R01–R06) over the raw bank CSV, flagging suspicious
transactions. RiskRanker scores accounts worst-first into one case. CaseActor
assigns a disposition—escalate, freeze, or monitor—logging the rules that fired.
NarrativeWriter composes the signable SAR memo. Each handoff is memory, not glue
code.
