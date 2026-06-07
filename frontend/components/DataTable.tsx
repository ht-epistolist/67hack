"use client";

import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/types";
import { cn } from "@/lib/utils";

const PAGE = 50;
const NUMERIC = new Set(["amount"]);
const MONO = new Set(["txn_id", "account_id", "counterparty_id", "amount", "device_id"]);

type Page = { columns: string[]; rows: (string | number)[][]; total: number; offset: number };

export function DataTable({ datasetKey }: { datasetKey: string }) {
  const [page, setPage] = useState<Page | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => setOffset(0), [datasetKey]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/api/rows?offset=${offset}&limit=${PAGE}`)
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled) setPage(d);
      })
      .catch(() => {})
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [offset, datasetKey]);

  const total = page?.total ?? 0;
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + PAGE, total);

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card/40">
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full border-collapse text-[12.5px]">
          <thead className="sticky top-0 z-10 bg-card">
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="w-12 px-3 py-2.5 text-right font-medium">#</th>
              {page?.columns.map((c) => (
                <th key={c} className="whitespace-nowrap px-3 py-2.5 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {page?.rows.map((row, i) => (
              <tr key={offset + i} className="border-b border-border/60 hover:bg-accent/40">
                <td className="px-3 py-2 text-right font-mono text-[11px] text-muted-foreground/60">
                  {offset + i + 1}
                </td>
                {row.map((cell, j) => {
                  const col = page.columns[j];
                  const isAcct = col === "counterparty_id" && String(cell).startsWith("AC-");
                  return (
                    <td
                      key={j}
                      className={cn(
                        "whitespace-nowrap px-3 py-2 text-foreground/90",
                        MONO.has(col) && "font-mono text-[11.5px]",
                        NUMERIC.has(col) && "tabular-nums",
                        isAcct && "text-primary"
                      )}
                    >
                      {col === "amount" ? `$${Number(cell).toLocaleString()}` : String(cell)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between border-t border-border px-4 py-2.5 text-[12px] text-muted-foreground">
        <span className="flex items-center gap-2">
          {loading && <Loader2 size={12} className="spin" />}
          Showing {start.toLocaleString()}–{end.toLocaleString()} of {total.toLocaleString()} rows
        </span>
        <span className="flex items-center gap-1">
          <button
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE))}
            className="grid h-7 w-7 place-items-center rounded-md hover:bg-accent disabled:opacity-30"
          >
            <ChevronLeft size={15} />
          </button>
          <span className="px-1 tabular-nums">
            {Math.floor(offset / PAGE) + 1} / {Math.max(1, Math.ceil(total / PAGE))}
          </span>
          <button
            disabled={end >= total}
            onClick={() => setOffset(offset + PAGE)}
            className="grid h-7 w-7 place-items-center rounded-md hover:bg-accent disabled:opacity-30"
          >
            <ChevronRight size={15} />
          </button>
        </span>
      </div>
    </div>
  );
}
