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

It is deliberately **hybrid**: LLM agents *reason and decide*, deterministic
Python tools do the *exact math*, and **ring membership is anchored to the
engine's candidate** — the Skeptic may only prune members that have no concrete
tie, so LLM variance can never drop a genuine member.

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
                          ┌────────────────────────┐ membership anchored to the
                          │   Risk Synthesizer      │ engine candidate; a member
                          │   (REASONING_MODEL)     │ stays unless the Skeptic
                          └───────────┬────────────┘ vetoes it AND it has no tie
                                      ▼              → ring + internal exposure
                       Verdict  →  streamed over WebSocket  →  Live UI
```

### Models (OpenRouter → Google Gemini)
LLM calls go through **OpenRouter** (OpenAI-compatible API at
`https://openrouter.ai/api/v1`) to **Google Gemini** (routed via the user's
Vertex integration on OpenRouter). Two roles, two models:

| Role | Setting | Default model | Used for |
|---|---|---|---|
| Specialist tool-calling loops | `AGENT_MODEL` | `google/gemini-2.5-flash` | the chatty per-agent reason → call-tool → reason loop |
| Reasoning / synthesis | `REASONING_MODEL` | `google/gemini-2.5-pro` | each agent's structured JSON conclusion + the Synthesizer's case narrative |
| Cognee memory embeddings | `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` (384-dim) | **local fastembed** — *not* via OpenRouter (it has no embeddings endpoint), zero tokens, fully offline |

Only **`OPENROUTER_API_KEY`** is required for live reasoning. With **no key**,
`llm.available()` is false and every agent runs its **deterministic analysis
path** instead — the pipeline still completes end-to-end and passes the
benchmark. (`COGNEE_LLM_MODEL` is only touched by Cognee's optional graph
narration; the core write/recall path never needs an LLM.)

### The flow, step by step
1. **Memory online.** The orchestrator (Lead Investigator) boots Cognee and
   embeds the account/transfer graph with fastembed into Cognee's Kuzu (graph)
   + LanceDB (vector) stores.
2. **Engine surfaces a candidate.** The unsupervised detector runs (features →
   robust anomaly → coordination graph → strong-edge communities → scored
   candidates) and emits its single top **candidate cluster**.
3. **Six agents examine that candidate, concurrently.** 5 corroborator
   specialists + 1 Adversarial Skeptic each run an **LLM tool-calling loop**
   (deterministic fallback if no key): they're handed the candidate + recalled
   peer findings, call deterministic analytics tools, then emit a short
   structured conclusion. Each **writes its finding to Cognee** and **recalls
   peers' findings** semantically — genuine cross-agent shared memory.
4. **Synthesizer fuses the verdict.** The Risk Synthesizer keeps a candidate
   member if ≥1 corroborator lens supports it **and** the Skeptic didn't prune
   it — but membership is **anchored to the engine candidate**: the Skeptic's
   veto only sticks for members with *no* concrete tie (peer transfer, shared
   cohort, or mule role). Exposure is the confirmed ring's internal
   peer-transfer flow. The verdict streams over WebSocket to the live UI.

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

**Per-agent LLM mechanics.** Each agent gets the case brief, the engine
candidate, and its semantically-recalled peer findings, then runs a bounded
function-calling loop (`AGENT_MODEL`, up to 6 tool iterations) over its lens
tools — the exact math is done in Python, the LLM just decides what to look at
and what it means. It then produces a short **structured JSON conclusion**
(`REASONING_MODEL`: `title`, `summary`, `flagged_accounts`, `confidence`). The
finding's **`signal` label is fixed to the agent's lens** (e.g. Network →
`account_to_account_transfers`, Skeptic → `skeptic_veto`) — it is *not*
LLM-chosen — so the synthesizer always knows which lens corroborated which
member. Any LLM/tool error falls back to that agent's deterministic path.

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
- **LLM:** Google **Gemini** via **OpenRouter** (OpenAI-compatible) —
  `AGENT_MODEL` (flash) for specialist loops, `REASONING_MODEL` (pro) for synthesis
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
OpenRouter routes to **Google Gemini** (via your Vertex integration):
`AGENT_MODEL=google/gemini-2.5-flash` drives the specialists' tool-calling loops
and `REASONING_MODEL=google/gemini-2.5-pro` the structured conclusions +
synthesis — change either in `.env` to taste. Cognee's embeddings always run
**locally via fastembed** (no embeddings call goes to OpenRouter), so memory is
free and offline regardless. The header shows **"Gemini reasoning live"** once a
key is detected.

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
