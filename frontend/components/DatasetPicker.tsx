"use client";

import { Check, Plus } from "lucide-react";
import { useRef, useState } from "react";
import type { Dataset } from "@/lib/types";
import { cn } from "@/lib/utils";

export function DatasetPicker({
  datasets,
  busy,
  onSelect,
  onUpload,
}: {
  datasets: Dataset[];
  busy: boolean;
  onSelect: (id: string) => void;
  onUpload: (file: File) => Promise<{ ok: boolean; error?: string }>;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="mx-auto max-w-4xl">
      <h2 className="text-lg font-semibold text-foreground">Datasets</h2>
      <p className="mt-1 text-[13px] text-muted-foreground">
        Select a case to investigate, or add your own CSV.
      </p>

      <div className="mt-6 flex flex-col gap-2">
        {datasets.map((d) => (
          <button
            key={d.id}
            disabled={busy}
            onClick={() => onSelect(d.id)}
            className={cn(
              "group flex items-center gap-4 rounded-xl border bg-card/40 px-4 py-3.5 text-left transition-colors hover:bg-accent/40 disabled:opacity-60",
              d.active ? "border-primary/50" : "border-border"
            )}
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium text-foreground">{d.name}</span>
                {d.active && <Check size={13} className="text-primary" />}
              </div>
              <p className="truncate text-[12px] text-muted-foreground">{d.description}</p>
            </div>
            {d.summary && (
              <div className="hidden items-center gap-6 text-right sm:flex">
                <Stat value={d.summary.transactions.toLocaleString()} label="rows" />
                <Stat value={d.summary.total_accounts_seen} label="accounts" />
                <Stat value={`${d.summary.window_days}d`} label="window" />
              </div>
            )}
          </button>
        ))}

        <button
          disabled={busy}
          onClick={() => fileRef.current?.click()}
          className="flex items-center gap-2 rounded-xl border border-dashed border-border px-4 py-3 text-[13px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground disabled:opacity-60"
        >
          <Plus size={15} /> Add CSV
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={async (e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (!f) return;
            setError(null);
            const res = await onUpload(f);
            if (!res.ok) setError(res.error ?? "Upload failed.");
          }}
        />
      </div>

      {error && (
        <div className="mt-3 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-[12px] text-destructive">
          {error}
        </div>
      )}
    </div>
  );
}

function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="w-16">
      <div className="text-sm font-semibold tabular-nums text-foreground">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
    </div>
  );
}
