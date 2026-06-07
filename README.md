# frtc — Multi-Agent Fraud Investigator (Track 02)

A sophisticated **multi-agent AI system** that autonomously hunts a coordinated
fraud ring hidden in 90 days of bank transactions — with a **live UI** that shows
the agents reasoning in real time and **Cognee** as the shared agent memory /
knowledge graph.

> **Track 02 — Fraud Watch (Crestline Community Bank).** 5,000 transactions,
> ~300 accounts. Somewhere inside: a ring that never tripped an alert threshold.
> Hint: ~12 accounts, exposure ≈ $161,751.

**What the system finds (autonomously):** a **10-account ring** moving
**$161,750.90** across **250 peer transfers** — exactly matching the benchmark.

### Works on any similar dataset
The system isn't hard-coded to Track 02. Pick a dataset in the UI (**Datasets →
Explore → Investigation** tabs), or drop in your own CSV (same schema), and it
investigates *that* data on its own merits — detectors are **adaptive** (structuring
finds whatever round threshold a ring hugs; timing flags concentration in any hours;
the cohort is found by age-gap), and the case brief is derived from the loaded data.
A second bundled dataset, **Synthetic — Ring B** (7 accounts, ~$4.8k structuring,
late-night, ~$732k exposure), is discovered at 100% precision/recall — proving no
answer is baked in.

---

## How it works

The system assumes **only the dataset's structure** — never its content. An
unsupervised engine discovers candidate rings from anomaly + coordination
structure; agents then **corroborate or refute** each candidate, an adversarial
**Skeptic** prunes weak members, and a synthesizer confirms the ring. No account
ids, amounts, hours or dates are baked in; answer keys live only in `eval.py`.

```
                 ┌──────────────────────────────────────────────┐
   STEP 1        │  Unsupervised engine  (numpy + networkx)       │
  discover       │  • population-relative features (no constants) │
                 │  • robust anomaly score per account            │
                 │  • coordination graph: transfers · shared      │
                 │    device · open-date cohort · fingerprint sim │
                 │  • strong-edge communities → candidate cluster │
                 └───────────────────────┬──────────────────────┘
   STEP 2                                 ▼  candidate members
  corroborate    ┌─────────┬────────┬────────┬──────────┬─────────┐
   / refute      ▼         ▼        ▼        ▼          ▼         ▼
            Network   Mule     Temporal  Structuring Profiler  ADVERSARIAL
            Analyst   Hunter   Analyst   Analyst     Profiler   SKEPTIC
              │  each: drill into the candidate, support/refute per member │
              ▼         ▼        ▼        ▼          ▼         ▼ (vetoes)
              └──────────────►  COGNEE shared memory  ◄────────────────┘
                          (typed graph + semantic recall, fastembed)
   STEP 3                              │
  confirm                             ▼
                          ┌────────────────────────┐
                          │   Risk Synthesizer      │ keep members corroborated
                          │                         │ by ≥1 lens & not vetoed →
                          └───────────┬────────────┘ ring + exposure
                                      ▼
                       Verdict  →  streamed over WebSocket  →  Live UI
```

### Why it's content-agnostic (bulletproof)
Every cut-off is a **percentile or gap of the data at hand** — anomaly is
median/MAD z-scores in the fraud-suspicious direction; the "freshly-opened cohort"
is found by an age-gap; "structuring" is amounts hugging *any* round threshold the
account never crosses; "synchronized" is timing concentration vs. the population.
Ring **membership** comes only from *strong* collusion evidence (peer transfers,
shared devices, shared cohort); behavioural similarity informs ranking but can't
admit innocent look-alikes. On a ring-free dataset the engine yields **zero**
candidates.

### The agents (corroborate / refute / drill in)
| Agent | Role |
|---|---|
| **Lead Investigator** | runs the engine, dispatches corroboration |
| **Network Analyst** | confirms which members are wired together by peer transfers |
| **Mule Hunter** | confirms receive-only mules & receive-then-forward layering hops |
| **Temporal Analyst** | confirms abnormally concentrated, synchronized timing |
| **Structuring Analyst** | confirms amounts pinned under a round threshold |
| **Account Profiler** | confirms freshly-opened cohort & shared infrastructure |
| **Adversarial Skeptic** | argues each member is *innocent* and prunes the weakly-linked |
| **Risk Synthesizer** | keeps members corroborated by ≥1 lens & not vetoed; computes exposure |

Agents can **drill into any account**, **compare a set**, **expand a suspect's
neighborhood**, and **score the coordination of an arbitrary set** to test
hypotheses — so the verdict is *earned by corroboration*, not assembled from
fixed rules.

### Why Cognee
Each agent **writes its findings to Cognee** (typed `Finding` nodes), and agents
**recall peers' findings via semantic search** before they start — genuine
cross-agent shared memory, not isolated runs. The account/transfer **knowledge
graph** is also built in Cognee (Kuzu graph + LanceDB vectors). Embeddings run
**locally via fastembed**, so memory works offline and costs zero tokens.

---

## Tech stack
- **Backend:** Python · FastAPI · WebSocket streaming · pandas · networkx
- **Memory:** Cognee 1.1 (local Kuzu + LanceDB + SQLite, fastembed embeddings)
- **LLM:** Google Vertex (Gemini) via **OpenRouter** (OpenAI-compatible)
- **Frontend:** Next.js 16 · React 19 · Tailwind v4 · React Flow · Framer Motion

---

## Run it

### 1. Backend
```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # first run also pulls fastembed (~90MB)

cp .env.example .env                              # then add your OpenRouter key (below)
.venv/bin/python -m uvicorn app.main:app --port 8000
```

### 2. Frontend
```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

Open **http://localhost:3000** and click **Run Investigation**. Watch the agents
light up the graph as the ring emerges, then read the verdict.

### Enabling Gemini reasoning (optional)
The system runs fully in **deterministic mode with no key** (and still passes the
benchmark). To turn on live LLM reasoning + narrative, put your **OpenRouter API
key** in `backend/.env`:
```bash
OPENROUTER_API_KEY=sk-or-v1-...
```
Models default to your **Google Vertex** models via OpenRouter
(`google/gemini-2.5-flash` for the specialists, `google/gemini-2.5-pro` for the
synthesizer) — change `AGENT_MODEL` / `REASONING_MODEL` in `.env` to taste. The
header shows **"Gemini reasoning live"** once a key is detected.

---

## Benchmark
```bash
cd backend && .venv/bin/python eval.py            # Track 02 (default)
cd backend && .venv/bin/python eval.py ring_b     # the synthetic dataset
```
Runs the full investigation and, when the dataset has a known answer key, scores
the verdict (precision / recall / exposure). Both bundled datasets pass at
**100% precision & recall** (Track 02 exposure $161,750.90). Datasets without a key
(e.g. uploads) just report findings.

## Project layout
```
backend/app/
  engine/       unsupervised detector: features → anomaly → coordination
                graph → strong-edge communities → scored candidate rings
  data/         loader (swappable active dataset + schema validation),
                datasets registry, synthetic-dataset generator
  tools/        adaptive analytics + drill-down (compare / neighborhood /
                shared-infra / coordination-score) the agents investigate with
  memory/       Cognee shared memory (typed graph + semantic recall)
  agents/       base loop, corroborator specialists + skeptic, synthesizer
  main.py       FastAPI: REST + WebSocket + dataset select/upload
frontend/
  lib/          WebSocket hook + types (state derived from the event log)
  components/   DatasetPicker, NetworkGraph, AgentRoster, ReasoningFeed, VerdictPanel
```

Regenerate the synthetic dataset with `cd backend && python -m app.data.generate_synthetic`.
