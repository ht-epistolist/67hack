"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  API_BASE,
  WS_URL,
  type AgentState,
  type Dataset,
  type DataSummary,
  type GraphData,
  type InvEvent,
  type Overview,
  type Verdict,
} from "./types";

// Static roster (colors mirror the backend agents) so cards render immediately.
const ROSTER: Omit<AgentState, "status" | "action" | "toolCalls" | "flagged">[] = [
  { key: "orchestrator", name: "Lead Investigator", role: "Runs the engine, dispatches corroboration", color: "#a78bfa" },
  { key: "network", name: "Network Analyst", role: "Corroborates peer-transfer money flow", color: "#6366f1" },
  { key: "mule_hunter", name: "Mule Hunter", role: "Confirms mules & layering hops", color: "#ec4899" },
  { key: "temporal", name: "Temporal Analyst", role: "Confirms synchronized timing", color: "#f59e0b" },
  { key: "structuring", name: "Structuring Analyst", role: "Confirms threshold-hugging amounts", color: "#10b981" },
  { key: "profiler", name: "Account Profiler", role: "Confirms cohort & shared infrastructure", color: "#06b6d4" },
  { key: "skeptic", name: "Adversarial Skeptic", role: "Argues innocence; prunes weak members", color: "#a855f7" },
  { key: "synthesizer", name: "Risk Synthesizer", role: "Fuses corroboration into a verdict", color: "#ef4444" },
];

export type FlagState = {
  account_id: string;
  signals: string[];
  agents: string[];
  weight: number;
  inRing: boolean;
};

function clip(s: unknown, n = 120): string {
  const str = String(s ?? "");
  return str.length > n ? str.slice(0, n - 1) + "…" : str;
}

export function useInvestigation() {
  const [summary, setSummary] = useState<DataSummary | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [events, setEvents] = useState<InvEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [started, setStarted] = useState(false);
  const [busy, setBusy] = useState(false);
  const seen = useRef<Set<string>>(new Set());
  const wsRef = useRef<WebSocket | null>(null);

  const refetchData = useCallback(async () => {
    const [s, o, g] = await Promise.all([
      fetch(`${API_BASE}/api/summary`).then((r) => r.json()),
      fetch(`${API_BASE}/api/overview`).then((r) => r.json()),
      fetch(`${API_BASE}/api/graph`).then((r) => r.json()),
    ]);
    setSummary(s);
    setOverview(o);
    setGraph(g);
  }, []);

  const loadDatasets = useCallback(async () => {
    const d = await fetch(`${API_BASE}/api/datasets`).then((r) => r.json());
    setDatasets(d.datasets ?? []);
  }, []);

  // Initial load.
  useEffect(() => {
    refetchData().catch(() => {});
    loadDatasets().catch(() => {});
  }, [refetchData, loadDatasets]);

  const resetRun = useCallback(() => {
    seen.current.clear();
    setEvents([]);
    setStarted(false);
  }, []);

  const selectDataset = useCallback(
    async (id: string) => {
      setBusy(true);
      try {
        await fetch(`${API_BASE}/api/datasets/select`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id }),
        });
        resetRun();
        await Promise.all([refetchData(), loadDatasets()]);
      } finally {
        setBusy(false);
      }
    },
    [refetchData, loadDatasets, resetRun]
  );

  const uploadDataset = useCallback(
    async (file: File): Promise<{ ok: boolean; error?: string }> => {
      setBusy(true);
      try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await fetch(`${API_BASE}/api/datasets/upload`, { method: "POST", body: fd });
        if (!res.ok) {
          const detail = await res.json().catch(() => ({}));
          return { ok: false, error: detail.detail || `upload failed (${res.status})` };
        }
        resetRun();
        await Promise.all([refetchData(), loadDatasets()]);
        return { ok: true };
      } finally {
        setBusy(false);
      }
    },
    [refetchData, loadDatasets, resetRun]
  );

  // WebSocket.
  useEffect(() => {
    let stop = false;
    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!stop) setTimeout(connect, 1500);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (m) => {
        const evt: InvEvent = JSON.parse(m.data);
        const key = `${evt.ts}-${evt.type}-${evt.agent ?? ""}-${
          (evt.account_id as string) ?? ""
        }-${(evt.tool as string) ?? ""}-${(evt.title as string) ?? ""}`;
        if (seen.current.has(key)) return;
        seen.current.add(key);
        setEvents((prev) => [...prev, evt]);
      };
    }
    connect();
    return () => {
      stop = true;
      wsRef.current?.close();
    };
  }, []);

  const start = useCallback(async () => {
    seen.current.clear();
    setEvents([]);
    setStarted(true);
    await fetch(`${API_BASE}/api/investigate`, { method: "POST" }).catch(() => {});
  }, []);

  // Derive agent states from the event log.
  const agents: AgentState[] = useMemo(() => {
    const map = new Map<string, AgentState>(
      ROSTER.map((r) => [r.key, { ...r, status: "idle", action: "", toolCalls: 0, flagged: [] }])
    );
    for (const e of events) {
      const a = e.agent ? map.get(e.agent) : undefined;
      if (!a) continue;
      switch (e.type) {
        case "agent_started":
          a.status = "running";
          a.action = "Investigating…";
          break;
        case "thought":
          a.action = clip(e.text);
          break;
        case "tool_call":
          a.toolCalls += 1;
          a.action = `Running ${e.tool}()…`;
          break;
        case "tool_result":
          a.action = `${e.tool}: ${clip(e.summary, 80)}`;
          break;
        case "memory_read":
          a.action = "Recalling shared memory…";
          break;
        case "finding":
          a.action = clip(e.title, 90);
          break;
        case "agent_done":
          a.status = "done";
          a.flagged = (e.flagged as string[]) ?? a.flagged;
          a.action = clip(e.summary, 110);
          break;
      }
    }
    // Orchestrator status from phases.
    const orch = map.get("orchestrator")!;
    const phases = events.filter((e) => e.type === "status");
    if (phases.length) {
      const last = phases[phases.length - 1];
      orch.status = last.phase === "done" ? "done" : "running";
      orch.action = clip(last.message, 110);
    }
    return Array.from(map.values());
  }, [events]);

  // Derive per-account flag state.
  const flags: Record<string, FlagState> = useMemo(() => {
    const f: Record<string, FlagState> = {};
    let ring: string[] = [];
    for (const e of events) {
      if (e.type === "flag_account") {
        const id = e.account_id as string;
        const sig = e.signal as string;
        f[id] ??= { account_id: id, signals: [], agents: [], weight: 0, inRing: false };
        if (sig && !f[id].signals.includes(sig)) f[id].signals.push(sig);
        if (e.agent && !f[id].agents.includes(e.agent)) f[id].agents.push(e.agent);
        f[id].weight = Math.max(f[id].weight, Number(e.weight) || 0);
      }
      if (e.type === "verdict") ring = (e.ring as string[]) ?? [];
    }
    for (const id of ring) {
      f[id] ??= { account_id: id, signals: [], agents: [], weight: 1, inRing: false };
      f[id].inRing = true;
    }
    return f;
  }, [events]);

  const verdict: Verdict | null = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i].type === "verdict") return events[i] as unknown as Verdict;
    }
    return null;
  }, [events]);

  const phase = useMemo(() => {
    const ph = events.filter((e) => e.type === "status");
    return ph.length ? (ph[ph.length - 1].phase as string) : "ready";
  }, [events]);

  const running = started && phase !== "done";

  // Step model for the progress stepper.
  const specialists = agents.filter(
    (a) => a.key !== "orchestrator" && a.key !== "synthesizer"
  );
  const specialistsDone = specialists.filter((a) => a.status === "done").length;
  const progress = useMemo(() => {
    const memDone = events.some((e) => e.type === "status" && e.phase === "memory_ready");
    const engineDone = events.some((e) => e.type === "candidate" || (e.type === "status" && e.phase === "no_ring"));
    const synthStarted = events.some((e) => e.type === "status" && e.phase === "synthesis");
    let active = -1;
    if (started) active = 0;
    if (memDone) active = 1;
    if (engineDone || specialistsDone > 0) active = 2;
    if (synthStarted) active = 3;
    if (verdict) active = 4;
    return {
      active,
      specialistsDone,
      specialistsTotal: specialists.length,
      steps: [
        { key: "memory", label: "Build memory" },
        { key: "engine", label: "Engine scan" },
        { key: "corroborate", label: `Corroborate (${specialistsDone}/${specialists.length})` },
        { key: "synthesis", label: "Synthesize" },
        { key: "verdict", label: "Verdict" },
      ],
    };
  }, [events, started, verdict, specialistsDone, specialists.length]);

  return {
    summary,
    overview,
    graph,
    datasets,
    events,
    agents,
    flags,
    verdict,
    phase,
    progress,
    running,
    started,
    busy,
    connected,
    start,
    selectDataset,
    uploadDataset,
  };
}
