# FRTC — Devpost submission

**Live demo → https://fraudwatch-one.vercel.app**

Four agents turn 5,000 raw bank transactions into one ranked, pre-justified
fraud-ring case — for the analyst who has three minutes.

---

## Inspiration

We talked to the reality of a community-bank fraud analyst: a queue of automated
alerts, all day, with about three minutes per case. The rules these teams run
fire on _single_ transactions, so an analyst sees thousands of disconnected rows
and never the shape between them.

The rings that actually cost money are built to exploit exactly that blind spot.
Every transfer is parked just under the $1,000 review trigger. The money fans
out across mule accounts. The accounts never form a tidy round-trip cycle you
could grep for. Reconstructing that by hand takes longer than three minutes, so
the case gets cleared as noise — and the ring keeps running.

We wanted to flip the analyst's job from _discovering_ the ring to _confirming_
one that's already been found, ranked, and justified.

## What it does

FRTC runs a four-agent pipeline that collaborates through a shared Cognee memory
graph. Each agent reads the previous agent's node and writes its own, so the
handoff is _memory_, not in-process strings:

1. **FraudFinder — Find it.** Reads the Crestline Community Bank CSV and runs
   deterministic detectors R01–R06 (pandas + networkx), writing flagged
   transactions and per-account signals.
2. **RiskRanker — Rank it.** Scores every account worst-first and writes one
   ranked case plus the ring hypothesis.
3. **CaseActor — Act on it.** Assigns a disposition (ESCALATE-SAR /
   FREEZE-pending / MONITOR), logging the exact rule IDs that fired as the
   reason.
4. **NarrativeWriter — Explain it.** Composes a downloadable, signable SAR memo
   through OpenRouter.

The analyst gets one ranked case (RING-001) in a Next.js console: a money-path
graph, a per-account "why flagged" table, a disposition with its rule IDs, and a
downloadable memo — plus a live "Ask the Analyst" feature for follow-up
questions.

The headline result, re-derived from the raw CSV with nothing hardcoded:
**$161,750.90** in exposure across **250 sub-threshold transfers** (every one in
the $402–$899 band), moved by **10 coordinated accounts** through **3 directed
layering chains** — matching the hidden Kaggle answer key **to the cent**.

## How we built it

- **The detectors are deterministic.** R01–R06 run in plain pandas and networkx
  over the actual Kaggle dataset — sub-threshold structuring, fan-out, layering
  chains, onboarding bursts. Nothing about the ring is hardcoded; it's
  re-derived every run.
- **The agents share memory, not function calls.** Cognee is the substrate. Each
  agent tags and writes its findings to the graph; the next agent reads that
  node. The collaboration is inspectable after the fact.
- **The LLM writes prose, not verdicts.** OpenRouter powers the SAR narrative and
  the live "Ask the Analyst" feature, but every _decision_ traces to a
  deterministic rule ID, so the explanation never depends on a model's mood.
- **The console is a Next.js + React + TypeScript app** styled with Tailwind v4,
  deployed on Vercel. Data is served from Neon (serverless Postgres) with a
  graceful fallback to bundled JSON when `DATABASE_URL` is unset, so the demo
  never breaks.

## Challenges we ran into

- **Matching the answer key to the cent.** The hint said "approximately 12"
  accounts; the data has 10. We found the ring reserves the contiguous block
  AC-0001..AC-0012, but AC-0004 and AC-0008 never exist in the data — 12 reserved
  IDs minus 2 intentional gaps = 10 real accounts. Proving that meant our
  computed total had to land on $161,750.90 exactly, not "about right."
- **Sub-threshold detection without false-positive floods.** A naive "near
  $1,000" rule lights up half the bank. Getting the $402–$899 structuring band to
  surface the ring and stay quiet on legitimate traffic took real tuning.
- **Making collaboration real, not theater.** It's easy to call four functions in
  a row and say "multi-agent." Routing every handoff through tagged Cognee memory
  nodes — so an agent genuinely consumes the prior agent's output as memory —
  was the harder, truer design.
- **Keeping everything explainable.** Every flag and disposition had to log the
  exact rule that fired (R01–R08), because a SAR you can't justify is a SAR you
  can't file.

## Accomplishments that we're proud of

- **To the cent, nothing hardcoded.** The exposure, account count, and chain
  structure are all re-derived from the raw CSV and match the hidden key exactly.
- **A genuine memory-based handoff** between four agents through Cognee — not glue
  code wearing an agent costume.
- **A deployed console an analyst could actually drive** in three minutes: ranked
  worst-first, money-path graph, "why flagged" table, signable memo.
- **End-to-end explainability** — every decision on screen points at the rule
  that produced it.

## What we learned

- Fraud is a **graph problem** wearing a tabular disguise. Rules on single rows
  miss coordinated rings by construction, not by accident.
- **Memory-as-handoff** is a cleaner multi-agent pattern than passing strings:
  the trail is inspectable, and agents stay decoupled.
- **Explainability is a feature, not overhead.** Pairing deterministic detectors
  with an LLM that only writes the narrative gives you output that's both
  trustworthy and readable.
- A demo that **degrades gracefully** (Neon → bundled JSON) is worth more than one
  that's impressive until the database hiccups.

## What's next for FRTC

- **Generalization beyond the seed dataset** — we've started with ring C/D/E and a
  clean control to prove the detectors aren't overfit to RING-001.
- **More detectors** — explicit cycle/SCC detection, temporal burst analysis, and
  threshold auto-tuning per institution.
- **Real-time ingestion** instead of a batch CSV, so cases surface as the money
  moves.
- **An analyst feedback loop** — confirmed/dismissed dispositions feeding back into
  the ranking model.
- **Production hooks** — connect to live case-management systems and SAR e-filing,
  with multi-tenant, role-based access.

## Built With

**Languages:** Python, TypeScript, JavaScript, SQL

**Frameworks & UI:** Next.js, React, Tailwind CSS v4, react-markdown / remark-gfm,
lucide-react

**Agents & AI:** Cognee (shared agent memory graph), OpenRouter (LLM provider),
OpenAI SDK (client)

**Data & detection:** pandas, networkx, NumPy, Kaggle (Track-02 dataset)

**Database:** Neon (serverless Postgres) via @neondatabase/serverless

**Platform & tooling:** Vercel (hosting), Bun (JS runtime/package manager),
uv (Python runner), Trupeer (demo video), Geodo (domain research)
