"use client";

import { useEffect, useRef } from "react";
import {
  Brain,
  CheckCircle2,
  Cpu,
  FileSearch,
  Flag,
  Gavel,
  Network,
  Play,
  Radar,
  Wrench,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { InvEvent } from "@/lib/types";

const ICONS: Record<string, React.ElementType> = {
  status: Play,
  ml_step: Cpu,
  candidate: Radar,
  plan: Network,
  agent_started: Play,
  thought: Brain,
  tool_call: Wrench,
  tool_result: Wrench,
  memory_read: FileSearch,
  finding: Flag,
  agent_done: CheckCircle2,
  verdict: Gavel,
};

function line(e: InvEvent): { text: string; dim?: boolean } | null {
  switch (e.type) {
    case "status":
      return { text: String(e.message ?? "") };
    case "ml_step":
      return { text: String(e.message ?? "") };
    case "candidate":
      return { text: String(e.message ?? "Engine flagged a candidate cluster.") };
    case "plan":
      return { text: String(e.message ?? "Dispatching specialists.") };
    case "agent_started":
      return { text: `${e.agent_name} started — ${e.role}` };
    case "thought":
      return { text: String(e.text ?? "") };
    case "tool_call":
      return { text: `${e.agent_name} → ${e.tool}(${fmtArgs(e.args)})`, dim: true };
    case "tool_result":
      return { text: `${e.tool} ⇒ ${e.summary}`, dim: true };
    case "memory_read":
      return {
        text: `${e.agent_name} recalled ${(e.hits as unknown[])?.length ?? 0} prior finding(s) from Cognee`,
        dim: true,
      };
    case "finding":
      return { text: `${e.agent_name}: ${e.title} — ${e.text}` };
    case "agent_done":
      return { text: `${e.agent_name} concluded.`, dim: true };
    case "verdict":
      return {
        text: `VERDICT — ring of ${e.ring_size} accounts, $${Number(e.exposure).toLocaleString()} exposure.`,
      };
    default:
      return null;
  }
}

function fmtArgs(args: unknown): string {
  if (!args || typeof args !== "object") return "";
  return Object.entries(args as Record<string, unknown>)
    .map(([k, v]) => `${k}=${Array.isArray(v) ? `[${v.length}]` : v}`)
    .join(", ")
    .slice(0, 48);
}

export function ReasoningFeed({ events }: { events: InvEvent[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [events.length]);

  const shown = events.filter((e) => line(e) !== null);

  return (
    <div className="flex h-full flex-col">
      <h2 className="px-1 pb-2 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        Live reasoning
      </h2>
      <div ref={ref} className="flex-1 space-y-1.5 overflow-y-auto pr-1">
        {shown.length === 0 && (
          <div className="px-1 text-sm text-muted-foreground">
            Press <span className="text-foreground">Run Investigation</span> to watch the agents
            reason in real time.
          </div>
        )}
        {shown.map((e, i) => {
          const Icon = ICONS[e.type] ?? Brain;
          const l = line(e)!;
          const isVerdict = e.type === "verdict";
          const isFinding = e.type === "finding";
          return (
            <div
              key={`${e.ts}-${i}`}
              className={cn(
                "feed-enter flex gap-2 rounded-md px-2.5 py-1.5 text-[12px] leading-snug",
                isVerdict
                  ? "border-l-2 border-threat bg-accent/50 font-medium text-foreground"
                  : isFinding
                  ? "border border-border bg-accent/30 text-foreground"
                  : l.dim
                  ? "text-muted-foreground"
                  : "text-foreground/85"
              )}
            >
              <Icon size={14} className="mt-0.5 shrink-0 opacity-60" />
              <span className="min-w-0">{l.text}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
