"use client";

import { Database, Radar, Table2 } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ThemeToggle } from "./ThemeToggle";
import { cn } from "@/lib/utils";

export type View = "datasets" | "data" | "investigation";

const ITEMS: { key: View; label: string; icon: React.ElementType }[] = [
  { key: "datasets", label: "Datasets", icon: Database },
  { key: "data", label: "Data", icon: Table2 },
  { key: "investigation", label: "Investigation", icon: Radar },
];

export function IconRail({
  view,
  onSelect,
  investigationEnabled,
}: {
  view: View;
  onSelect: (v: View) => void;
  investigationEnabled: boolean;
}) {
  return (
    <nav className="flex h-full w-14 shrink-0 flex-col items-center gap-1 border-r border-border bg-sidebar py-3">
      <div className="mb-2 grid h-9 w-9 place-items-center rounded-lg bg-primary/15 font-mono text-[11px] font-bold tracking-tight text-primary">
        ƒ
      </div>
      {ITEMS.map((it) => {
        const disabled = it.key === "investigation" && !investigationEnabled;
        const active = view === it.key;
        return (
          <Tooltip key={it.key}>
            <TooltipTrigger asChild>
              <button
                disabled={disabled}
                onClick={() => onSelect(it.key)}
                className={cn(
                  "grid h-9 w-9 place-items-center rounded-lg transition-colors",
                  active
                    ? "bg-accent text-foreground"
                    : disabled
                    ? "text-muted-foreground/30"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                )}
              >
                <it.icon size={17} />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">{it.label}</TooltipContent>
          </Tooltip>
        );
      })}
      <div className="mt-auto">
        <ThemeToggle />
      </div>
    </nav>
  );
}
