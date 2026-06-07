"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentState } from "@/lib/types";

function dotClass(status: AgentState["status"]) {
  if (status === "running") return "bg-primary animate-pulse";
  if (status === "done") return "bg-primary";
  return "bg-muted-foreground/30";
}

export function AgentRoster({ agents }: { agents: AgentState[] }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  return (
    <div className="flex flex-col gap-1">
      <h2 className="px-1 pb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        Agents
      </h2>
      {agents.map((a) => {
        const text = a.action || a.role;
        const isOpen = !!expanded[a.key];
        return (
          <div
            key={a.key}
            className={cn(
              "rounded-lg border px-3 py-2.5 transition-colors",
              a.status === "running" ? "border-border bg-accent/40" : "border-transparent"
            )}
          >
            <div className="flex items-center gap-2">
              <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", dotClass(a.status))} />
              <span className="truncate text-[13px] font-medium text-foreground">{a.name}</span>
              {a.flagged.length > 0 && (
                <span className="ml-auto text-[11px] tabular-nums text-muted-foreground">
                  {a.flagged.length} flagged
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={() => setExpanded((prev) => ({ ...prev, [a.key]: !prev[a.key] }))}
              aria-expanded={isOpen}
              className="mt-0.5 flex w-full items-start gap-1 pl-3.5 text-left text-[11px] text-muted-foreground transition-colors hover:text-foreground"
            >
              <ChevronRight
                className={cn(
                  "mt-0.5 h-3 w-3 shrink-0 transition-transform",
                  isOpen && "rotate-90"
                )}
              />
              <span className={cn("min-w-0", isOpen ? "whitespace-normal break-words" : "truncate")}>
                {text}
              </span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
