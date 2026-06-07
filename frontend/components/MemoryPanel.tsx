"use client";

import { useMemo } from "react";
import { Brain, GitBranch, Save } from "lucide-react";
import type { InvEvent } from "@/lib/types";

export function MemoryPanel({ events }: { events: InvEvent[] }) {
  const mem = useMemo(() => {
    let nodes = 0;
    let edges = 0;
    let backend = "";
    const findings: {
      agent: string;
      title: string;
      accounts: string[];
      confidence: number;
      signal: string;
    }[] = [];
    let recalls = 0;
    for (const e of events) {
      if (e.type === "status" && e.phase === "memory_ready") {
        nodes = Number(e.graph_nodes) || 0;
        edges = Number(e.graph_edges) || 0;
        backend = String(e.backend || "");
      }
      if (e.type === "finding") {
        findings.push({
          agent: String(e.agent_name),
          title: String(e.title),
          accounts: (e.accounts as string[]) ?? [],
          confidence: Number(e.confidence) || 0,
          signal: String(e.signal),
        });
      }
      if (e.type === "memory_read") recalls += 1;
    }
    return { nodes, edges, backend, findings, recalls };
  }, [events]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-1 pb-2">
        <Brain size={13} className="text-primary" />
        <h2 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Cognee shared memory
        </h2>
        {mem.backend && (
          <span className="ml-auto rounded-full border border-border px-2 py-0.5 text-[10px] text-muted-foreground">
            {mem.backend}
          </span>
        )}
      </div>

      <div className="mb-2 grid grid-cols-3 gap-2 px-1">
        <MiniStat icon={GitBranch} value={`${mem.nodes}/${mem.edges}`} label="graph n/e" />
        <MiniStat icon={Save} value={mem.findings.length} label="findings" />
        <MiniStat icon={Brain} value={mem.recalls} label="recalls" />
      </div>

      <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto pr-1">
        {mem.findings.length === 0 && (
          <p className="px-1 text-[12px] text-muted-foreground">
            Agents write findings here as they investigate; peers recall them before acting.
          </p>
        )}
        {mem.findings.map((f, i) => (
          <div key={i} className="rounded-lg border border-border bg-card/40 px-2.5 py-2">
            <div className="flex items-center gap-2">
              <span className="truncate text-[12px] font-medium text-foreground">{f.title}</span>
              <span className="ml-auto shrink-0 text-[10px] tabular-nums text-muted-foreground">
                {Math.round(f.confidence * 100)}%
              </span>
            </div>
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              {f.agent} · {f.accounts.length} account{f.accounts.length === 1 ? "" : "s"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MiniStat({
  icon: Icon,
  value,
  label,
}: {
  icon: React.ElementType;
  value: string | number;
  label: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card/40 px-2 py-1.5">
      <div className="flex items-center gap-1 text-foreground">
        <Icon size={11} className="text-muted-foreground" />
        <span className="text-[13px] font-semibold tabular-nums">{value}</span>
      </div>
      <div className="text-[9px] uppercase tracking-wide text-muted-foreground">{label}</div>
    </div>
  );
}
