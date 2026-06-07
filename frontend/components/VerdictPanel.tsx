"use client";

import { AnimatePresence, motion, useMotionValue, animate } from "framer-motion";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Verdict } from "@/lib/types";

const SIGNAL_LABEL: Record<string, string> = {
  account_to_account_transfers: "peer transfers",
  mule: "mule / layering",
  off_hours: "off-hours",
  structuring: "structuring",
  new_account_cohort: "new-account cohort",
};

function AnimatedNumber({ value, prefix = "", decimals = 0 }: { value: number; prefix?: string; decimals?: number }) {
  const mv = useMotionValue(0);
  const [display, setDisplay] = useState("0");
  useEffect(() => {
    const controls = animate(mv, value, {
      duration: 1.1,
      ease: "easeOut",
      onUpdate: (v) =>
        setDisplay(v.toLocaleString(undefined, { maximumFractionDigits: decimals, minimumFractionDigits: decimals })),
    });
    return controls.stop;
  }, [value, decimals, mv]);
  return (
    <span>
      {prefix}
      {display}
    </span>
  );
}

export function VerdictPanel({
  verdict,
  onClose,
}: {
  verdict: Verdict | null;
  onClose: () => void;
}) {
  return (
    <AnimatePresence>
      {verdict && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 z-20 flex items-center justify-center bg-background/70 p-6 backdrop-blur-sm"
        >
          <motion.div
            initial={{ scale: 0.94, y: 16, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ scale: 0.96, opacity: 0 }}
            transition={{ type: "spring", stiffness: 260, damping: 24 }}
            className="relative max-h-[86vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-border bg-card p-6 shadow-2xl"
          >
            <button
              onClick={onClose}
              className="absolute right-4 top-4 text-muted-foreground transition-colors hover:text-foreground"
            >
              <X size={18} />
            </button>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-threat" />
              <span className="text-sm font-semibold text-foreground">Verdict</span>
              <span className="text-[12px] text-muted-foreground">coordinated ring confirmed</span>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-3">
              <Stat label="Ring size">
                <AnimatedNumber value={verdict.ring_size} /> accounts
              </Stat>
              <Stat label="Exposure" accent>
                <AnimatedNumber value={verdict.exposure} prefix="$" decimals={2} />
              </Stat>
              <Stat label="Confidence">
                <AnimatedNumber value={Math.round(verdict.confidence * 100)} />%
              </Stat>
            </div>

            {verdict.candidate_size != null && (
              <p className="mt-3 text-[11px] text-muted-foreground">
                Engine proposed{" "}
                <span className="text-foreground">{verdict.candidate_size}</span> candidate(s);
                agents confirmed <span className="text-foreground">{verdict.ring_size}</span>
                {verdict.pruned && verdict.pruned.length > 0 && (
                  <>
                    {" "}· skeptic pruned{" "}
                    <span className="text-foreground">{verdict.pruned.join(", ")}</span>
                  </>
                )}
                {verdict.engine?.evidence_kinds?.length ? (
                  <> · evidence: {verdict.engine.evidence_kinds.join(", ")}</>
                ) : null}
              </p>
            )}

            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{verdict.narrative}</p>

            <h3 className="mt-5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Flagged accounts
            </h3>
            <div className="mt-2 overflow-hidden rounded-lg border border-border">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="h-8">Account</TableHead>
                    <TableHead className="h-8">Signals</TableHead>
                    <TableHead className="h-8 text-right">Risk</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {verdict.per_account.map((p) => (
                    <TableRow key={p.account_id}>
                      <TableCell className="py-1.5 font-mono text-threat">{p.account_id}</TableCell>
                      <TableCell className="py-1.5 text-muted-foreground">
                        {p.signals.map((s) => SIGNAL_LABEL[s] ?? s).join(", ")}
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-muted-foreground">
                        {p.risk_score.toFixed(2)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Stat({
  label,
  children,
  accent,
}: {
  label: string;
  children: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-background/50 px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div
        className={`mt-0.5 text-lg font-bold ${accent ? "text-threat" : "text-foreground"}`}
      >
        {children}
      </div>
    </div>
  );
}
