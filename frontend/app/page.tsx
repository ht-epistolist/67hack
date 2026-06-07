"use client";

import { useEffect, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { AgentRoster } from "@/components/AgentRoster";
import { DataPanel } from "@/components/DataPanel";
import { DataTable } from "@/components/DataTable";
import { DatasetPicker } from "@/components/DatasetPicker";
import { IconRail, type View } from "@/components/IconRail";
import { MemoryPanel } from "@/components/MemoryPanel";
import { NetworkGraph } from "@/components/NetworkGraph";
import { PhaseStepper } from "@/components/PhaseStepper";
import { ReasoningFeed } from "@/components/ReasoningFeed";
import { VerdictPanel } from "@/components/VerdictPanel";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useInvestigation } from "@/lib/useInvestigation";

export default function Home() {
  const inv = useInvestigation();
  const [view, setView] = useState<View>("datasets");
  const [showVerdict, setShowVerdict] = useState(false);
  const [rightTab, setRightTab] = useState<"reasoning" | "memory">("reasoning");

  useEffect(() => {
    if (inv.verdict && inv.started) setShowVerdict(true);
  }, [inv.verdict, inv.started]);

  const datasetName = inv.summary?.dataset?.name ?? "—";
  const datasetId = inv.summary?.dataset?.id ?? "none";
  const ringIds = inv.verdict?.ring ?? [];

  const launch = () => {
    setShowVerdict(true);
    inv.start();
    setView("investigation");
  };

  return (
    <main className="flex h-screen overflow-hidden">
      <IconRail view={view} onSelect={setView} investigationEnabled={!!inv.graph} />

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Quiet top bar */}
        <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border px-4">
          <span className="text-sm font-medium text-foreground">{datasetName}</span>
          {inv.summary && (
            <span className="text-[12px] text-muted-foreground">
              {inv.summary.transactions.toLocaleString()} rows · {inv.summary.total_accounts_seen} accounts
            </span>
          )}
          <div className="ml-auto" />
          {view !== "datasets" && (
            <Button size="sm" onClick={launch} disabled={inv.running || inv.busy} className="gap-2">
              {inv.running ? (
                <>
                  <Loader2 size={14} className="spin" /> Investigating
                </>
              ) : (
                <>
                  <Sparkles size={14} /> Run investigation
                </>
              )}
            </Button>
          )}
        </header>

        <div className="min-h-0 flex-1 overflow-hidden">
          {view === "datasets" && (
            <div className="h-full overflow-y-auto px-6 py-8">
              <DatasetPicker
                datasets={inv.datasets}
                busy={inv.busy}
                onSelect={(id) => {
                  inv.selectDataset(id);
                  setView("data");
                }}
                onUpload={async (f) => {
                  const r = await inv.uploadDataset(f);
                  if (r.ok) setView("data");
                  return r;
                }}
              />
            </div>
          )}

          {view === "data" && (
            <div className="grid h-full grid-cols-[1fr_340px] gap-3 p-3">
              <DataTable datasetKey={datasetId} />
              <aside className="min-h-0 overflow-y-auto rounded-xl border border-border bg-card/40 p-3">
                <DataPanel summary={inv.summary} overview={inv.overview} />
              </aside>
            </div>
          )}

          {view === "investigation" && (
            <div className="grid h-full grid-cols-[248px_1fr_360px] gap-3 p-3">
              <aside className="min-h-0 overflow-y-auto pr-1">
                <AgentRoster agents={inv.agents} />
              </aside>
              <section className="relative min-h-0 overflow-hidden rounded-xl border border-border bg-card/40">
                <NetworkGraph graph={inv.graph} flags={inv.flags} ringIds={ringIds} />
                {inv.started && (
                  <div className="pointer-events-none absolute left-1/2 top-3 z-10 -translate-x-1/2">
                    <PhaseStepper steps={inv.progress.steps} active={inv.progress.active} />
                  </div>
                )}
                {!inv.started && (
                  <div className="pointer-events-none absolute left-1/2 top-4 z-10 -translate-x-1/2 rounded-full border border-border bg-card/80 px-3 py-1.5 text-[11px] text-muted-foreground backdrop-blur">
                    Transfer network · Run investigation to begin
                  </div>
                )}
                <VerdictPanel verdict={showVerdict ? inv.verdict : null} onClose={() => setShowVerdict(false)} />
                {inv.verdict && !showVerdict && (
                  <button
                    onClick={() => setShowVerdict(true)}
                    className="absolute right-3 top-3 z-10 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent"
                  >
                    View verdict
                  </button>
                )}
              </section>
              <aside className="flex min-h-0 flex-col rounded-xl border border-border bg-card/40 p-3">
                <div className="mb-2 flex items-center gap-1 rounded-lg border border-border bg-background/60 p-0.5">
                  {(["reasoning", "memory"] as const).map((t) => (
                    <button
                      key={t}
                      onClick={() => setRightTab(t)}
                      className={cn(
                        "flex-1 rounded-md px-2 py-1 text-[12px] font-medium capitalize transition-colors",
                        rightTab === t
                          ? "bg-accent text-foreground"
                          : "text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {t === "memory" ? "Cognee memory" : "Reasoning"}
                    </button>
                  ))}
                </div>
                <div className="min-h-0 flex-1">
                  {rightTab === "reasoning" ? (
                    <ReasoningFeed events={inv.events} />
                  ) : (
                    <MemoryPanel events={inv.events} />
                  )}
                </div>
              </aside>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
