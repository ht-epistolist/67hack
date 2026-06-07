"use client";

import { Handle, Position } from "@xyflow/react";
import { motion } from "framer-motion";
import { memo } from "react";
import type { FlagState } from "@/lib/useInvestigation";

export type AccountNodeData = {
  label: string;
  inNetwork: boolean;
  receiverOnly: boolean;
  recent: boolean;
  flag?: FlagState;
};

function colorFor(data: AccountNodeData): { bg: string; ring: string; glow: string } {
  const sigs = data.flag?.signals.length ?? 0;
  if (data.flag?.inRing)
    return { bg: "var(--threat)", ring: "color-mix(in oklch, var(--threat) 55%, white)", glow: "0 0 10px -2px color-mix(in oklch, var(--threat) 55%, transparent)" };
  if (sigs >= 3)
    return { bg: "var(--threat-2)", ring: "color-mix(in oklch, var(--threat-2) 50%, white)", glow: "none" };
  if (sigs === 2)
    return { bg: "var(--threat-2)", ring: "color-mix(in oklch, var(--warn) 55%, white)", glow: "none" };
  if (sigs === 1)
    return { bg: "var(--warn)", ring: "color-mix(in oklch, var(--warn) 50%, white)", glow: "none" };
  if (data.inNetwork)
    return { bg: "color-mix(in oklch, var(--signal) 40%, var(--card))", ring: "var(--signal)", glow: "none" };
  return { bg: "var(--muted)", ring: "var(--border)", glow: "none" };
}

function AccountNodeImpl({ data }: { data: AccountNodeData }) {
  const c = colorFor(data);
  const sigs = data.flag?.signals.length ?? 0;
  const size = data.flag?.inRing ? 34 : data.inNetwork ? 28 : 16;
  const short = data.label.replace("AC-", "");
  return (
    <motion.div
      key={`${data.label}-${sigs}-${data.flag?.inRing}`}
      initial={false}
      animate={{ scale: data.flag ? [1.4, 1] : 1 }}
      transition={{ type: "spring", stiffness: 320, damping: 16 }}
      className={data.flag?.inRing ? "pulse-ring" : ""}
      style={{
        width: size,
        height: size,
        borderRadius: data.receiverOnly ? 6 : 999,
        background: c.bg,
        border: `2px solid ${c.ring}`,
        boxShadow: c.glow,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transform: data.receiverOnly ? "rotate(45deg)" : undefined,
        transition: "background .4s ease, border-color .4s ease, box-shadow .4s ease",
        position: "relative",
      }}
      title={`${data.label}${data.receiverOnly ? " · receiver-only mule" : ""}${
        data.flag?.signals.length ? " — " + data.flag.signals.join(", ") : ""
      }`}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
      {(data.inNetwork || data.flag) && (
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            color: sigs > 0 || data.flag?.inRing ? "white" : "var(--foreground)",
            transform: data.receiverOnly ? "rotate(-45deg)" : undefined,
            fontFamily: "var(--font-mono)",
          }}
        >
          {short}
        </span>
      )}
      {data.recent && !data.flag?.inRing && (
        <span
          style={{
            position: "absolute",
            inset: -5,
            borderRadius: data.receiverOnly ? 8 : 999,
            border: "1.5px dashed color-mix(in oklch, var(--warn) 70%, transparent)",
            pointerEvents: "none",
          }}
        />
      )}
    </motion.div>
  );
}

export const AccountNode = memo(AccountNodeImpl);
