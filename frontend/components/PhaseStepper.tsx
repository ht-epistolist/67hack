"use client";

import { Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

type Step = { key: string; label: string };

export function PhaseStepper({
  steps,
  active,
}: {
  steps: Step[];
  active: number;
}) {
  return (
    <div className="flex items-center gap-1.5 rounded-full border border-border bg-card/80 px-2 py-1.5 backdrop-blur">
      {steps.map((s, i) => {
        const done = i < active;
        const current = i === active;
        return (
          <div key={s.key} className="flex items-center gap-1.5">
            <div
              className={cn(
                "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors",
                done && "text-safe",
                current && "bg-primary/15 text-foreground",
                !done && !current && "text-muted-foreground"
              )}
            >
              <span
                className={cn(
                  "grid h-4 w-4 place-items-center rounded-full border text-[9px] font-bold",
                  done && "border-safe bg-safe/20 text-safe",
                  current && "border-primary text-primary",
                  !done && !current && "border-border"
                )}
              >
                {done ? <Check size={10} /> : current ? <Loader2 size={10} className="spin" /> : i + 1}
              </span>
              <span className="whitespace-nowrap">{s.label}</span>
            </div>
            {i < steps.length - 1 && (
              <span
                className={cn(
                  "h-px w-4 transition-colors",
                  i < active ? "bg-safe" : "bg-border"
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
