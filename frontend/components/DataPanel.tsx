"use client";

import { motion } from "framer-motion";
import { Clock, Globe, Layers, Wallet } from "lucide-react";
import type { DataSummary, Overview } from "@/lib/types";

const FOREIGN = new Set(["JP", "FR", "UK", "DE", "CN"]);

export function DataPanel({
  summary,
  overview,
}: {
  summary: DataSummary | null;
  overview: Overview | null;
}) {
  if (!overview || !summary) {
    return <div className="p-4 text-sm text-muted-foreground">Loading case data…</div>;
  }

  const maxHour = Math.max(...overview.hours.map((h) => h.count), 1);
  const maxCat = Math.max(...overview.categories.map((c) => c.count), 1);
  const maxRegion = Math.max(...overview.regions.map((r) => r.count), 1);

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto pr-1">
      <SectionLabel icon={Layers}>Case data</SectionLabel>

      <div className="grid grid-cols-2 gap-2">
        <Tile label="Transactions" value={summary.transactions.toLocaleString()} />
        <Tile label="Accounts" value={summary.total_accounts_seen} />
        <Tile label="Peer transfers" value={summary.a2a_transactions} />
        <Tile label="Window" value={`${overview.window_days} days`} />
      </div>

      {/* Hour-of-day histogram — the overnight anomaly */}
      <Card>
        <SectionLabel icon={Clock} sub={`${Math.round(overview.night_share * 100)}% overnight (00–06h)`}>
          Activity by hour
        </SectionLabel>
        <div className="mt-2 flex h-24 items-end gap-[2px]">
          {overview.hours.map((h) => {
            const night = h.hour < 6;
            return (
              <motion.div
                key={h.hour}
                initial={{ height: 0 }}
                animate={{ height: `${(h.count / maxHour) * 100}%` }}
                transition={{ delay: h.hour * 0.012, type: "spring", stiffness: 200, damping: 22 }}
                className="flex-1 rounded-sm"
                style={{
                  background: night ? "var(--warn)" : "color-mix(in oklch, var(--signal) 55%, transparent)",
                  minHeight: 2,
                }}
                title={`${String(h.hour).padStart(2, "0")}:00 — ${h.count} txns`}
              />
            );
          })}
        </div>
        <div className="mt-1 flex justify-between font-mono text-[9px] text-muted-foreground">
          <span>00h</span>
          <span>06h</span>
          <span>12h</span>
          <span>18h</span>
          <span>23h</span>
        </div>
      </Card>

      {/* Merchant categories */}
      <Card>
        <SectionLabel icon={Wallet}>Merchant categories</SectionLabel>
        <div className="mt-2 space-y-1.5">
          {overview.categories.map((c) => (
            <Bar key={c.name} label={c.name} value={c.count} max={maxCat} tone="signal" />
          ))}
        </div>
      </Card>

      {/* Regions */}
      <Card>
        <SectionLabel icon={Globe} sub="foreign regions flagged">IP regions</SectionLabel>
        <div className="mt-2 space-y-1.5">
          {overview.regions.map((r) => (
            <Bar
              key={r.name}
              label={r.name}
              value={r.count}
              max={maxRegion}
              tone={FOREIGN.has(r.name) ? "warn" : "muted"}
            />
          ))}
        </div>
      </Card>

      {/* Amount scale */}
      <Card>
        <SectionLabel icon={Wallet}>Transaction amounts</SectionLabel>
        <div className="mt-2 grid grid-cols-3 gap-2 font-mono text-xs">
          <Mini label="median" value={`$${overview.amounts.p50}`} />
          <Mini label="p99" value={`$${overview.amounts.p99.toLocaleString()}`} />
          <Mini label="max" value={`$${overview.amounts.max.toLocaleString()}`} />
        </div>
        <p className="mt-2 text-[11px] leading-snug text-muted-foreground">
          A freshly-opened cohort of{" "}
          <span className="text-warn">{overview.cohort_size} accounts</span> appears just before
          the window — a lead worth pulling.
        </p>
      </Card>
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card/60 p-3">{children}</div>
  );
}

function SectionLabel({
  children,
  icon: Icon,
  sub,
}: {
  children: React.ReactNode;
  icon: React.ElementType;
  sub?: string;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <Icon size={13} className="text-muted-foreground" />
      <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        {children}
      </span>
      {sub && <span className="ml-auto text-[10px] text-warn">{sub}</span>}
    </div>
  );
}

function Tile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-border bg-card/60 px-3 py-2">
      <div className="font-display text-xl font-bold text-foreground">{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
    </div>
  );
}

function Bar({
  label,
  value,
  max,
  tone,
}: {
  label: string;
  value: number;
  max: number;
  tone: "signal" | "warn" | "muted";
}) {
  const color =
    tone === "warn"
      ? "var(--warn)"
      : tone === "signal"
      ? "color-mix(in oklch, var(--signal) 70%, transparent)"
      : "var(--muted-foreground)";
  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className="w-20 shrink-0 truncate text-muted-foreground">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${(value / max) * 100}%` }}
          transition={{ type: "spring", stiffness: 160, damping: 24 }}
          className="h-full rounded-full"
          style={{ background: color }}
        />
      </div>
      <span className="w-9 shrink-0 text-right font-mono text-muted-foreground">{value}</span>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-background/60 px-2 py-1.5 text-center">
      <div className="text-foreground">{value}</div>
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</div>
    </div>
  );
}
