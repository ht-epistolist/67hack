# FRTC — Devpost submission

**Live demo → https://frtc-fraud-investigator-t8gb9.ondigitalocean.app/**

A multi-agent AI system that autonomously hunts a coordinated fraud ring no
alert threshold ever caught — and shows the agents reasoning, live.

## Inspiration

Community-bank fraud analysts get about three minutes per case, and their rules
fire on single transactions — so coordinated rings that keep every transfer
under the alert threshold and fan money across mules never trip a flag. We
wanted a system that hunts that invisible ring on its own and hands the analyst
a confirmed, justified verdict instead of raw rows.

## What it does

FRTC autonomously investigates 90 days of bank transactions and finds a
coordinated fraud ring no threshold caught. An unsupervised engine surfaces a
candidate cluster; then six specialist agents plus an adversarial Skeptic examine
it concurrently, each writing findings to a shared Cognee memory graph and
recalling each other's. A Risk Synthesizer fuses the verdict and streams it over
WebSocket to a live UI where the agents light up the graph in real time. On Track
02 it confirms a 10-account ring moving **$161,750.90** across **250 peer
transfers — matching the benchmark to the cent, nothing hardcoded.**

## How we built it

Hybrid by design: LLM agents (Google Gemini via OpenRouter) decide _what to look
at_, deterministic Python does the _exact math_, and ring membership is anchored
to the engine's candidate so model variance can never drop a real member. Memory
is Cognee (Kuzu graph + LanceDB vectors, fastembed embeddings running
locally/offline). Backend is FastAPI + WebSocket; frontend is Next.js 16 + React
Flow + Framer Motion. Deployed on DigitalOcean App Platform (Docker). With no API
key it runs fully deterministic and still passes the benchmark.

## Challenges we ran into

Making detection _content-agnostic_ — every cutoff is a percentile or gap of the
data at hand, so nothing is baked in (a ring-free dataset yields zero
candidates). Getting genuine cross-agent shared memory (concurrent agents
reading/writing Cognee semantically, not isolated runs). Keeping the LLM honest
by anchoring membership to the engine candidate and letting the Skeptic only
prune weakly-linked members. And deploying the heavy stack
(cognee/lancedb/kuzu/onnxruntime) on a 2 GB instance.

## Accomplishments that we're proud of

100% precision and recall on **two** datasets (Track 02 exposure to the cent,
plus a synthetic Ring B), genuine multi-agent shared memory, a fully
content-agnostic engine, a live real-time reasoning UI, and a deterministic
fallback that passes the benchmark with zero API keys and zero token cost.

## What we learned

Fraud is a coordination/graph problem disguised as rows. Anchoring LLM agents to
a deterministic candidate gives output that's both smart and trustworthy.
Memory-as-handoff (Cognee) beats glue code, and local fastembed embeddings keep
it cheap and offline.

## What's next for FRTC

Real-time/streaming ingestion, more drill-down tools and detectors, an analyst
feedback loop, and production SAR e-filing (we already email the SAR via Geo)
with multi-tenant access.

## Built With

python · typescript · fastapi · websocket · next.js · react · tailwindcss ·
react-flow · framer-motion · cognee · kuzu · lancedb · fastembed · google-gemini
· openrouter · pandas · numpy · networkx · digitalocean · docker · geo · kaggle ·
trupeer
