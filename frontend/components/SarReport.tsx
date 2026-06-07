"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Download, FileSignature, Loader2, Mail, Printer, Send, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { API_BASE, type Sar } from "@/lib/types";

const money = (n: number) =>
  n.toLocaleString(undefined, { style: "currency", currency: "USD" });
const num = (n: number) => n.toLocaleString();

/** A clickable [F-07] superscript that jumps to the finding within the sheet. */
function Cite({ id }: { id: string }) {
  return (
    <sup>
      <a
        href={`#finding-${id}`}
        onClick={(e) => {
          e.preventDefault();
          document
            .getElementById(`finding-${id}`)
            ?.scrollIntoView({ behavior: "smooth", block: "center" });
        }}
        className="ml-0.5 font-mono text-[10px] text-blue-700 no-underline hover:underline"
      >
        [{id}]
      </a>
    </sup>
  );
}

export function SarReport({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [sar, setSar] = useState<Sar | null>(null);
  const [loading, setLoading] = useState(false);
  const [examiner, setExaminer] = useState("");

  // Geo outreach (post-investigation: email the SAR via the connected Gmail).
  const [geo, setGeo] = useState<{
    enabled: boolean;
    gmail_connected?: boolean;
    from_email?: string;
    error?: string;
  } | null>(null);
  const [showGeo, setShowGeo] = useState(false);
  const [to, setTo] = useState("");
  const [sending, setSending] = useState(false);
  const [sendMsg, setSendMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    fetch(`${API_BASE}/api/sar`)
      .then((r) => r.json())
      .then((d: Sar) => setSar(d))
      .catch(() => setSar(null))
      .finally(() => setLoading(false));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    fetch(`${API_BASE}/api/geo/status`)
      .then((r) => r.json())
      .then((g) => {
        setGeo(g);
        if (g?.from_email) setTo((cur) => cur || g.from_email);
      })
      .catch(() => setGeo({ enabled: false }));
  }, [open]);

  const download = useCallback(() => {
    if (!sar || sar.status !== "ready") return;
    const html = buildSarHtml(sar, examiner);
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${sar.report_id}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }, [sar, examiner]);

  const print = useCallback(() => {
    if (!sar || sar.status !== "ready") return;
    const w = window.open("", "_blank", "width=820,height=1000");
    if (!w) return;
    w.document.write(buildSarHtml(sar, examiner));
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 250);
  }, [sar, examiner]);

  const ready = sar && sar.status === "ready";

  const sendViaGeo = useCallback(async () => {
    if (!ready || !to.trim() || sending) return;
    setSending(true);
    setSendMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/geo/send-sar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ to: to.trim(), examiner }),
      });
      const d = await res.json().catch(() => ({}));
      setSendMsg(
        res.ok
          ? { ok: true, text: `Sent to ${d.to}` }
          : { ok: false, text: d.detail || `Failed (${res.status})` }
      );
    } catch {
      setSendMsg({ ok: false, text: "Network error — could not reach the server." });
    } finally {
      setSending(false);
    }
  }, [ready, to, examiner, sending]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-6 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.96, y: 20, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ scale: 0.97, opacity: 0 }}
            transition={{ type: "spring", stiffness: 240, damping: 26 }}
            onClick={(e) => e.stopPropagation()}
            className="my-2 w-full max-w-3xl"
          >
            {/* Toolbar (dark, outside the paper) */}
            <div className="mb-3 flex items-center gap-2 text-zinc-200">
              <FileSignature size={16} />
              <span className="text-sm font-medium">Suspicious Activity Report</span>
              <div className="ml-auto flex items-center gap-2">
                {geo?.enabled && (
                  <button
                    onClick={() => setShowGeo((v) => !v)}
                    disabled={!ready}
                    title="Email this SAR via Geo (your connected Gmail)"
                    className="flex items-center gap-1.5 rounded-md border border-zinc-600 px-3 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 disabled:opacity-40"
                  >
                    <Mail size={14} /> Email via Geo
                  </button>
                )}
                <button
                  onClick={download}
                  disabled={!ready}
                  className="flex items-center gap-1.5 rounded-md bg-white px-3 py-1.5 text-xs font-medium text-zinc-900 transition-opacity hover:opacity-90 disabled:opacity-40"
                >
                  <Download size={14} /> Download HTML
                </button>
                <button
                  onClick={print}
                  disabled={!ready}
                  className="flex items-center gap-1.5 rounded-md border border-zinc-600 px-3 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 disabled:opacity-40"
                >
                  <Printer size={14} /> Print
                </button>
                <button
                  onClick={onClose}
                  className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
                  aria-label="Close report"
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            {/* Geo outreach panel: email the SAR via the connected Gmail */}
            {showGeo && ready && geo?.enabled && (
              <div className="mb-3 rounded-lg border border-zinc-700 bg-zinc-900/80 p-3 text-zinc-200">
                <div className="mb-2 flex items-center gap-2 text-xs text-zinc-400">
                  <Mail size={13} />
                  <span>
                    Email this SAR
                    {geo.from_email ? (
                      <>
                        {" "}from{" "}
                        <span className="font-mono text-zinc-300">{geo.from_email}</span>
                      </>
                    ) : null}{" "}
                    via Geo
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="email"
                    value={to}
                    onChange={(e) => setTo(e.target.value)}
                    placeholder="recipient@example.com"
                    className="min-w-[240px] flex-1 rounded-md border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-zinc-500"
                  />
                  <button
                    onClick={sendViaGeo}
                    disabled={sending || !to.trim() || geo.gmail_connected === false}
                    className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-40"
                  >
                    {sending ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <Send size={14} />
                    )}
                    {sending ? "Sending…" : "Send"}
                  </button>
                </div>
                {geo.gmail_connected === false && (
                  <p className="mt-2 text-xs text-amber-400">
                    No Gmail is connected in Geo — connect one in Geo settings to send.
                  </p>
                )}
                {sendMsg && (
                  <p className={`mt-2 text-xs ${sendMsg.ok ? "text-emerald-400" : "text-red-400"}`}>
                    {sendMsg.text}
                  </p>
                )}
                <p className="mt-2 text-[11px] text-zinc-500">
                  Sends a real email via your connected Gmail with the SAR summary,
                  narrative, subject accounts, and key findings.
                </p>
              </div>
            )}

            {/* The paper-white document (always light) */}
            <div className="rounded-lg bg-white text-zinc-900 shadow-2xl ring-1 ring-black/10">
              {loading && (
                <div className="flex items-center justify-center gap-2 px-10 py-24 text-zinc-500">
                  <Loader2 size={16} className="animate-spin" /> Assembling report…
                </div>
              )}

              {!loading && !ready && (
                <div className="px-10 py-24 text-center text-zinc-500">
                  No completed investigation yet. Run an investigation to generate the report.
                </div>
              )}

              {!loading && ready && <SarBody sar={sar} examiner={examiner} setExaminer={setExaminer} />}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function SarBody({
  sar,
  examiner,
  setExaminer,
}: {
  sar: Sar;
  examiner: string;
  setExaminer: (s: string) => void;
}) {
  const s = sar.summary;
  return (
    <div className="px-10 py-9 [font-feature-settings:'tnum']">
      {/* Letterhead */}
      <header className="border-b-2 border-zinc-900 pb-4">
        <div className="flex items-baseline justify-between">
          <h1 className="font-serif text-2xl font-semibold tracking-tight">
            Suspicious Activity Report
          </h1>
          <span className="font-mono text-sm text-zinc-500">{sar.report_id}</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-[13px] text-zinc-600">
          <span>
            Reporting source: <span className="text-zinc-900">{sar.institution.name}</span>
          </span>
          <span>
            Filed: <span className="font-mono text-zinc-900">{sar.filed_on}</span>
          </span>
          <span>
            Activity period:{" "}
            <span className="font-mono text-zinc-900">
              {sar.period.start.slice(0, 10)} → {sar.period.end.slice(0, 10)}
            </span>{" "}
            ({sar.period.days} days)
          </span>
        </div>
      </header>

      {/* Headline figures */}
      <section className="mt-6 grid grid-cols-4 gap-px overflow-hidden rounded-md bg-zinc-200 text-center">
        <Figure label="Subjects" value={`${s.ring_size}`} />
        <Figure label="Exposure" value={money(s.exposure)} strong />
        <Figure label="Peer transfers" value={num(s.transfer_count)} />
        <Figure label="Confidence" value={`${s.confidence_tier} · ${Math.round(s.confidence * 100)}%`} />
      </section>

      {/* I. Narrative */}
      <Part n="I" title="Summary of suspicious activity">
        <p className="text-[14px] leading-relaxed text-zinc-800">{sar.narrative}</p>
        {sar.findings.length > 0 && (
          <p className="mt-3 text-[12px] text-zinc-500">
            Supporting evidence:{" "}
            {sar.findings.map((f) => (
              <Cite key={f.id} id={f.id} />
            ))}
          </p>
        )}
        {s.candidate_size != null && (
          <p className="mt-2 text-[12px] text-zinc-500">
            The detection engine proposed {s.candidate_size} candidate account(s); corroboration and
            adversarial review confirmed {s.ring_size}
            {s.pruned && s.pruned.length > 0 && <> and pruned {s.pruned.join(", ")}</>}.
          </p>
        )}
      </Part>

      {/* II. Subjects */}
      <Part n="II" title="Subject accounts">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-zinc-300 text-left text-[11px] uppercase tracking-wide text-zinc-500">
              <th className="py-1.5 pr-2 font-medium">Account</th>
              <th className="py-1.5 pr-2 font-medium">Opened</th>
              <th className="py-1.5 pr-2 font-medium">Indicators</th>
              <th className="py-1.5 pr-2 font-medium">Evidence</th>
              <th className="py-1.5 font-medium">Recommended action</th>
            </tr>
          </thead>
          <tbody>
            {sar.subjects.map((sub) => (
              <tr key={sub.account_id} className="border-b border-zinc-100 align-top">
                <td className="py-2 pr-2 font-mono font-medium text-red-700">
                  {sub.account_id}
                  {sub.receiver_only && (
                    <span className="ml-1 align-middle text-[10px] font-normal text-zinc-400">
                      receiver-only
                    </span>
                  )}
                </td>
                <td className="py-2 pr-2 font-mono text-zinc-600">{sub.opened ?? "—"}</td>
                <td className="py-2 pr-2 text-zinc-700">{sub.signals.join(", ") || "—"}</td>
                <td className="py-2 pr-2">
                  {sub.citations.length ? (
                    sub.citations.map((c) => <Cite key={c} id={c} />)
                  ) : (
                    <span className="text-zinc-400">—</span>
                  )}
                </td>
                <td className="py-2 text-zinc-700">{sub.recommended_action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Part>

      {/* III. Evidence findings */}
      <Part n="III" title="Evidence">
        <div className="space-y-3">
          {sar.findings.map((f) => (
            <div
              key={f.id}
              id={`finding-${f.id}`}
              className={`scroll-mt-4 rounded-md border-l-2 py-1 pl-3 ${
                f.adversarial ? "border-amber-500 bg-amber-50/60" : "border-zinc-300"
              }`}
            >
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-[12px] font-medium text-zinc-500">{f.id}</span>
                <span className="text-[13px] font-medium text-zinc-900">{f.title}</span>
                <span className="ml-auto text-[11px] text-zinc-400">
                  {f.agent} · {f.signal_label}
                </span>
              </div>
              <p className="mt-0.5 text-[13px] leading-snug text-zinc-700">{f.text}</p>
              {f.accounts.length > 0 && (
                <p className="mt-1 font-mono text-[11px] text-zinc-500">{f.accounts.join(", ")}</p>
              )}
            </div>
          ))}
        </div>
      </Part>

      {/* IV. Method reliability + grounding */}
      <Part n="IV" title="Detection methods">
        <p className="mb-2 text-[12px] text-zinc-500">
          {sar.grounding.resolved} of {sar.grounding.claims} corroborating findings resolved against
          the confirmed ring.
        </p>
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-zinc-300 text-left text-[11px] uppercase tracking-wide text-zinc-500">
              <th className="py-1.5 pr-2 font-medium">Method</th>
              <th className="py-1.5 pr-2 text-right font-medium">Findings</th>
              <th className="py-1.5 text-right font-medium">Ring accounts</th>
            </tr>
          </thead>
          <tbody>
            {sar.methods.map((m) => (
              <tr key={m.signal} className="border-b border-zinc-100">
                <td className="py-1.5 pr-2 text-zinc-800">{m.label}</td>
                <td className="py-1.5 pr-2 text-right font-mono text-zinc-600">{m.findings}</td>
                <td className="py-1.5 text-right font-mono text-zinc-600">{m.ring_accounts}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Part>

      {/* V. Transaction appendix */}
      <Part n="V" title="Appendix — ring-internal transfers">
        <p className="mb-2 text-[12px] text-zinc-500">
          Showing {sar.appendix.shown} of {num(sar.appendix.total_internal_transfers)} peer transfers
          internal to the ring (the flow backing the exposure figure).
        </p>
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr className="border-b border-zinc-300 text-left text-[10px] uppercase tracking-wide text-zinc-500">
              {sar.appendix.columns.map((c) => (
                <th key={c} className="py-1 pr-2 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="font-mono">
            {sar.appendix.rows.map((row, i) => (
              <tr key={i} className="border-b border-zinc-100">
                {row.map((cell, j) => (
                  <td
                    key={j}
                    className={`py-1 pr-2 ${j === 3 ? "text-right tabular-nums" : "text-zinc-700"}`}
                  >
                    {j === 3 ? money(Number(cell)) : String(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </Part>

      {/* Signature */}
      <section className="mt-8 border-t border-zinc-300 pt-5">
        <div className="flex items-end justify-between gap-6">
          <div className="flex-1">
            <input
              value={examiner}
              onChange={(e) => setExaminer(e.target.value)}
              placeholder="Type your name to sign"
              className="w-full max-w-xs border-b border-zinc-400 bg-transparent pb-1 font-serif text-lg text-zinc-900 outline-none placeholder:font-sans placeholder:text-sm placeholder:text-zinc-400"
            />
            <p className="mt-1 text-[11px] uppercase tracking-wide text-zinc-500">
              Reviewing examiner
            </p>
          </div>
          <div className="text-right text-[12px] text-zinc-500">
            <p className="font-mono text-zinc-900">{sar.filed_on}</p>
            <p className="mt-1 text-[11px] uppercase tracking-wide">Date of filing</p>
          </div>
        </div>
        <p className="mt-5 text-[11px] leading-relaxed text-zinc-400">
          Machine-assisted analysis. Findings were generated by automated detection and
          multi-agent corroboration, then reviewed and signed by a human examiner before filing.
        </p>
      </section>
    </div>
  );
}

function Figure({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="bg-white px-3 py-3">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
      <div
        className={`mt-0.5 font-mono text-[15px] font-semibold tabular-nums ${
          strong ? "text-red-700" : "text-zinc-900"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function Part({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <section className="mt-7">
      <h2 className="mb-2.5 font-serif text-[15px] font-semibold text-zinc-900">
        <span className="text-zinc-400">{n}.</span> {title}
      </h2>
      {children}
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Standalone HTML export (Download + Print)                                  */
/* -------------------------------------------------------------------------- */

function esc(v: unknown): string {
  return String(v ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function buildSarHtml(sar: Sar, examiner: string): string {
  const s = sar.summary;
  const cite = (ids: string[]) =>
    ids.map((id) => `<sup><a href="#finding-${id}">[${esc(id)}]</a></sup>`).join(" ");

  const subjects = sar.subjects
    .map(
      (sub) => `<tr>
        <td class="mono red">${esc(sub.account_id)}${
        sub.receiver_only ? ' <span class="muted">receiver-only</span>' : ""
      }</td>
        <td class="mono">${esc(sub.opened ?? "—")}</td>
        <td>${esc(sub.signals.join(", ") || "—")}</td>
        <td>${cite(sub.citations) || "—"}</td>
        <td>${esc(sub.recommended_action)}</td>
      </tr>`
    )
    .join("");

  const findings = sar.findings
    .map(
      (f) => `<div class="finding${f.adversarial ? " adversarial" : ""}" id="finding-${esc(f.id)}">
        <div class="finding-head"><span class="mono muted">${esc(f.id)}</span>
        <strong>${esc(f.title)}</strong><span class="muted right">${esc(f.agent)} · ${esc(
        f.signal_label
      )}</span></div>
        <p>${esc(f.text)}</p>
        ${f.accounts.length ? `<p class="mono muted small">${esc(f.accounts.join(", "))}</p>` : ""}
      </div>`
    )
    .join("");

  const methods = sar.methods
    .map(
      (m) =>
        `<tr><td>${esc(m.label)}</td><td class="mono right">${m.findings}</td><td class="mono right">${m.ring_accounts}</td></tr>`
    )
    .join("");

  const appendix = sar.appendix.rows
    .map(
      (row) =>
        `<tr>${row
          .map((c, j) =>
            j === 3
              ? `<td class="mono right">${esc(money(Number(c)))}</td>`
              : `<td class="mono">${esc(c)}</td>`
          )
          .join("")}</tr>`
    )
    .join("");

  return `<!doctype html><html><head><meta charset="utf-8">
<title>${esc(sar.report_id)} — Suspicious Activity Report</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; background: #f4f4f5; color: #18181b;
    font: 14px/1.6 ui-sans-serif, system-ui, -apple-system, sans-serif; }
  .sheet { max-width: 760px; margin: 24px auto; background: #fff; padding: 48px 56px;
    box-shadow: 0 1px 3px rgba(0,0,0,.12); }
  h1 { font: 600 26px/1.1 Georgia, "Times New Roman", serif; margin: 0; letter-spacing: -.01em; }
  h2 { font: 600 16px Georgia, serif; margin: 28px 0 10px; }
  h2 .n { color: #a1a1aa; }
  .head { display:flex; justify-content:space-between; align-items:baseline;
    border-bottom: 2px solid #18181b; padding-bottom: 14px; }
  .meta { margin-top: 8px; color:#52525b; font-size: 13px; display:flex; gap:22px; flex-wrap:wrap; }
  .meta b { color:#18181b; font-weight:500; }
  .figs { display:grid; grid-template-columns: repeat(4,1fr); gap:1px; background:#e4e4e7;
    border:1px solid #e4e4e7; margin-top: 22px; }
  .fig { background:#fff; padding:12px; text-align:center; }
  .fig .l { font-size:10px; text-transform:uppercase; letter-spacing:.06em; color:#71717a; }
  .fig .v { font: 600 15px ui-monospace, "SF Mono", Menlo, monospace; margin-top:3px; }
  .fig .v.red { color:#b91c1c; }
  table { width:100%; border-collapse: collapse; font-size: 13px; margin-top: 4px; }
  th { text-align:left; font-size:10px; text-transform:uppercase; letter-spacing:.05em;
    color:#71717a; font-weight:500; border-bottom:1px solid #d4d4d8; padding:5px 8px 5px 0; }
  td { padding:6px 8px 6px 0; border-bottom:1px solid #f4f4f5; vertical-align: top; }
  .mono { font-family: ui-monospace, "SF Mono", Menlo, monospace; }
  .right { text-align:right; }
  .red { color:#b91c1c; font-weight:500; }
  .muted { color:#a1a1aa; font-weight: normal; }
  .small { font-size: 11px; }
  p { margin: 0 0 4px; }
  .finding { border-left: 2px solid #d4d4d8; padding: 2px 0 2px 12px; margin: 10px 0; }
  .finding.adversarial { border-color:#f59e0b; background:#fffbeb; }
  .finding-head { display:flex; gap:8px; align-items:baseline; }
  .finding-head .right { margin-left:auto; font-size:11px; }
  sup a { color:#1d4ed8; text-decoration:none; font: 500 10px ui-monospace, monospace; }
  .sign { margin-top: 36px; border-top:1px solid #d4d4d8; padding-top: 20px;
    display:flex; justify-content:space-between; align-items:flex-end; }
  .sign .name { font: 18px Georgia, serif; border-bottom:1px solid #71717a;
    min-width: 220px; padding-bottom: 3px; }
  .sign .cap { font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:#71717a; margin-top:4px; }
  .disc { margin-top: 18px; color:#a1a1aa; font-size: 11px; }
  @media print { body { background:#fff; } .sheet { box-shadow:none; margin:0; max-width:none; } }
</style></head>
<body><div class="sheet">
  <div class="head"><h1>Suspicious Activity Report</h1><span class="mono muted">${esc(
    sar.report_id
  )}</span></div>
  <div class="meta">
    <span>Reporting source: <b>${esc(sar.institution.name)}</b></span>
    <span>Filed: <b class="mono">${esc(sar.filed_on)}</b></span>
    <span>Activity period: <b class="mono">${esc(sar.period.start.slice(0, 10))} → ${esc(
    sar.period.end.slice(0, 10)
  )}</b> (${sar.period.days} days)</span>
  </div>

  <div class="figs">
    <div class="fig"><div class="l">Subjects</div><div class="v">${s.ring_size}</div></div>
    <div class="fig"><div class="l">Exposure</div><div class="v red">${esc(money(s.exposure))}</div></div>
    <div class="fig"><div class="l">Peer transfers</div><div class="v">${num(s.transfer_count)}</div></div>
    <div class="fig"><div class="l">Confidence</div><div class="v">${esc(s.confidence_tier)} · ${Math.round(
    s.confidence * 100
  )}%</div></div>
  </div>

  <h2><span class="n">I.</span> Summary of suspicious activity</h2>
  <p>${esc(sar.narrative)}</p>
  ${sar.findings.length ? `<p class="muted small">Supporting evidence: ${cite(
    sar.findings.map((f) => f.id)
  )}</p>` : ""}

  <h2><span class="n">II.</span> Subject accounts</h2>
  <table><thead><tr><th>Account</th><th>Opened</th><th>Indicators</th><th>Evidence</th><th>Recommended action</th></tr></thead>
  <tbody>${subjects}</tbody></table>

  <h2><span class="n">III.</span> Evidence</h2>
  ${findings}

  <h2><span class="n">IV.</span> Detection methods</h2>
  <p class="muted small">${sar.grounding.resolved} of ${sar.grounding.claims} corroborating findings resolved against the confirmed ring.</p>
  <table><thead><tr><th>Method</th><th class="right">Findings</th><th class="right">Ring accounts</th></tr></thead>
  <tbody>${methods}</tbody></table>

  <h2><span class="n">V.</span> Appendix — ring-internal transfers</h2>
  <p class="muted small">Showing ${sar.appendix.shown} of ${num(
    sar.appendix.total_internal_transfers
  )} peer transfers internal to the ring.</p>
  <table><thead><tr>${sar.appendix.columns
    .map((c) => `<th>${esc(c)}</th>`)
    .join("")}</tr></thead><tbody>${appendix}</tbody></table>

  <div class="sign">
    <div><div class="name">${esc(examiner) || "&nbsp;"}</div><div class="cap">Reviewing examiner</div></div>
    <div style="text-align:right"><div class="mono">${esc(
      sar.filed_on
    )}</div><div class="cap">Date of filing</div></div>
  </div>
  <p class="disc">Machine-assisted analysis. Findings were generated by automated detection and multi-agent corroboration, then reviewed and signed by a human examiner before filing.</p>
</div></body></html>`;
}
