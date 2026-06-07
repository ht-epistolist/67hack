"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Cpu, Loader2 } from "lucide-react";
import { API_BASE } from "@/lib/types";
import { cn } from "@/lib/utils";

type Msg = { role: "user" | "assistant"; content: string; tools?: string[] };

const SUGGESTIONS = [
  "Summarise the flagged ring",
  "Why was each account flagged?",
  "Are there any shared devices?",
  "What's unusual about the timing?",
];

export function ChatPanel() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [activity, setActivity] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, activity.length, streaming]);

  async function send(q: string) {
    const question = q.trim();
    if (!question || streaming) return;
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: "user", content: question }]);
    setInput("");
    setStreaming(true);
    setActivity([]);
    const used: string[] = [];
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ history, question }),
      });
      const reader = res.body!.getReader();
      const dec = new TextDecoder();
      let buf = "";
      let answered = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, idx).trim();
          buf = buf.slice(idx + 1);
          if (!line) continue;
          const evt = JSON.parse(line);
          if (evt.type === "tool") {
            used.push(evt.tool);
            setActivity((a) => [...a, `${evt.tool}(${fmtArgs(evt.args)})`]);
          } else if (evt.type === "tool_result") {
            setActivity((a) => [...a.slice(0, -1), `${evt.tool} ⇒ ${clip(evt.summary, 60)}`]);
          } else if (evt.type === "answer") {
            answered = true;
            setMessages((m) => [
              ...m,
              { role: "assistant", content: evt.text, tools: [...new Set(used)] },
            ]);
          }
        }
      }
      if (!answered)
        setMessages((m) => [...m, { role: "assistant", content: "(no answer)" }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Chat request failed." }]);
    } finally {
      setStreaming(false);
      setActivity([]);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <h2 className="px-1 pb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        Ask the case
      </h2>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
        {messages.length === 0 && !streaming && (
          <div className="space-y-2 px-1 pt-1">
            <p className="text-[12px] text-muted-foreground">
              Cross-question the investigation. Answers are grounded in the analytics
              tools + Cognee memory.
            </p>
            <div className="flex flex-col gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-lg border border-border bg-card/40 px-2.5 py-1.5 text-left text-[12px] text-foreground/80 transition-colors hover:border-primary/40 hover:text-foreground"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
            <div
              className={cn(
                "max-w-[92%] rounded-lg px-2.5 py-1.5 text-[12.5px] leading-snug",
                m.role === "user"
                  ? "bg-primary/15 text-foreground"
                  : "border border-border bg-card/40 text-foreground/90"
              )}
            >
              <span className="whitespace-pre-wrap break-words">{m.content}</span>
              {m.tools && m.tools.length > 0 && (
                <div className="mt-1 flex flex-wrap items-center gap-1 text-[10px] text-muted-foreground">
                  <Cpu size={10} />
                  {m.tools.join(", ")}
                </div>
              )}
            </div>
          </div>
        ))}

        {streaming && (
          <div className="flex justify-start">
            <div className="max-w-[92%] rounded-lg border border-border bg-card/40 px-2.5 py-1.5 text-[12px] text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Loader2 size={12} className="spin" />
                {activity.length ? activity[activity.length - 1] : "thinking…"}
              </span>
            </div>
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="mt-2 flex items-end gap-1.5"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the ring, an account, the data…"
          disabled={streaming}
          className="min-w-0 flex-1 rounded-lg border border-border bg-background px-2.5 py-2 text-[12.5px] text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/50 disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={streaming || !input.trim()}
          className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground transition hover:brightness-110 disabled:opacity-40"
        >
          <ArrowUp size={15} />
        </button>
      </form>
    </div>
  );
}

function fmtArgs(args: unknown): string {
  if (!args || typeof args !== "object") return "";
  return Object.entries(args as Record<string, unknown>)
    .map(([k, v]) => `${k}=${Array.isArray(v) ? `[${v.length}]` : v}`)
    .join(", ")
    .slice(0, 40);
}
function clip(s: unknown, n: number) {
  const str = String(s ?? "");
  return str.length > n ? str.slice(0, n - 1) + "…" : str;
}
