export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const WS_URL =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(
    /^http/,
    "ws"
  ) + "/ws";

export type InvEvent = {
  type: string;
  ts: number;
  agent?: string;
  agent_name?: string;
  [k: string]: unknown;
};

export type GraphNode = {
  id: string;
  x: number;
  y: number;
  in_network: boolean;
  receiver_only: boolean;
  recent: boolean;
  open_date: string | null;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  count: number;
  amount: number;
};

export type GraphData = { nodes: GraphNode[]; edges: GraphEdge[] };

export type AgentState = {
  key: string;
  name: string;
  role: string;
  color: string;
  status: "idle" | "running" | "done";
  action: string;
  toolCalls: number;
  flagged: string[];
};

export type Verdict = {
  ring: string[];
  ring_size: number;
  exposure: number;
  transfer_count: number;
  confidence: number;
  narrative: string;
  signals_used: string[];
  per_account: {
    account_id: string;
    risk_score: number;
    signal_count: number;
    signals: string[];
  }[];
  candidate_size?: number;
  pruned?: string[];
  engine?: {
    mean_anomaly: number | null;
    coordination_density: number | null;
    self_containment: number | null;
    evidence_kinds: string[];
  };
};

export type DataSummary = {
  transactions: number;
  originating_accounts: number;
  total_accounts_seen: number;
  window_start: string;
  window_end: string;
  a2a_transactions: number;
  llm_enabled: boolean;
  dataset?: { id: string; name: string };
};

export type Dataset = {
  id: string;
  name: string;
  description: string;
  active: boolean;
  uploaded: boolean;
  summary?: {
    transactions: number;
    total_accounts_seen: number;
    a2a_transactions: number;
    window_days: number;
  };
  error?: string;
};

export type Overview = {
  hours: { hour: number; count: number }[];
  categories: { name: string; count: number }[];
  regions: { name: string; count: number }[];
  amounts: { min: number; p50: number; p95: number; p99: number; max: number; mean: number };
  night_txns: number;
  night_share: number;
  cohort_size: number;
  cohort_accounts: string[];
  window_days: number;
};
