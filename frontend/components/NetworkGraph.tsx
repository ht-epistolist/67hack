"use client";

import "@xyflow/react/dist/style.css";
import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  ReactFlow,
  ReactFlowProvider,
  useNodesInitialized,
  useReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import { useEffect, useMemo } from "react";
import { AccountNode } from "./AccountNode";
import type { FlagState } from "@/lib/useInvestigation";
import type { GraphData } from "@/lib/types";

const nodeTypes = { account: AccountNode };

type Props = {
  graph: GraphData | null;
  flags: Record<string, FlagState>;
  ringIds: string[];
};

function Flow({ graph, flags, ringIds }: Props) {
  const { fitView } = useReactFlow();
  const nodesInitialized = useNodesInitialized();

  const nodes: Node[] = useMemo(() => {
    if (!graph) return [];
    return graph.nodes.map((n) => ({
      id: n.id,
      type: "account",
      position: { x: n.x, y: n.y },
      draggable: false,
      data: {
        label: n.id,
        inNetwork: n.in_network,
        receiverOnly: n.receiver_only,
        recent: n.recent,
        flag: flags[n.id],
      },
    }));
  }, [graph, flags]);

  const edges: Edge[] = useMemo(() => {
    if (!graph) return [];
    return graph.edges.map((e) => {
      const live = flags[e.source]?.inRing && flags[e.target]?.inRing;
      const hot =
        (flags[e.source]?.signals.length ?? 0) > 0 &&
        (flags[e.target]?.signals.length ?? 0) > 0;
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        animated: live,
        label: live ? `$${(e.amount / 1000).toFixed(1)}k` : undefined,
        labelStyle: { fill: "var(--threat)", fontSize: 9, fontFamily: "var(--font-mono)" },
        labelBgStyle: { fill: "var(--card)", fillOpacity: 0.85 },
        markerEnd: live
          ? { type: MarkerType.ArrowClosed, color: "var(--threat)", width: 16, height: 16 }
          : undefined,
        style: {
          stroke: live ? "var(--threat)" : hot ? "var(--threat-2)" : "var(--border)",
          strokeWidth: Math.min(6, 1 + Math.log10(e.amount + 1)),
          strokeDasharray: live ? "6 4" : undefined,
          animation: live ? "flow-dash 0.6s linear infinite" : undefined,
        },
      };
    });
  }, [graph, flags]);

  // Fit once the nodes are actually measured in the DOM.
  useEffect(() => {
    if (nodesInitialized) fitView({ padding: 0.18, duration: 300 });
  }, [nodesInitialized, fitView]);

  // Auto-focus the ring once the verdict lands.
  useEffect(() => {
    if (ringIds.length) {
      const t = setTimeout(
        () =>
          fitView({
            nodes: ringIds.map((id) => ({ id })),
            duration: 1000,
            padding: 0.5,
          }),
        500
      );
      return () => clearTimeout(t);
    }
  }, [ringIds, fitView]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.18 }}
      minZoom={0.2}
      maxZoom={2.5}
      proOptions={{ hideAttribution: true }}
      nodesConnectable={false}
      nodesDraggable={false}
      elementsSelectable={false}
    >
      <Background variant={BackgroundVariant.Dots} gap={26} size={1} color="var(--border)" />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

export function NetworkGraph(props: Props) {
  return (
    <div className="relative h-full w-full">
      <ReactFlowProvider>
        <Flow {...props} />
      </ReactFlowProvider>
      <Legend />
    </div>
  );
}

function Legend() {
  const items = [
    { c: "var(--muted)", t: "Normal account" },
    { c: "color-mix(in oklch, var(--signal) 45%, var(--card))", t: "In transfer network" },
    { c: "var(--warn)", t: "1 signal" },
    { c: "var(--threat-2)", t: "2+ signals" },
    { c: "var(--threat)", t: "Confirmed ring" },
  ];
  return (
    <div className="absolute bottom-3 left-3 flex flex-col gap-1.5 rounded-lg border border-border bg-card/85 px-3 py-2.5 text-[11px] backdrop-blur">
      {items.map((i) => (
        <div key={i.t} className="flex items-center gap-2 text-muted-foreground">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: i.c }} />
          {i.t}
        </div>
      ))}
      <div className="flex items-center gap-2 text-muted-foreground">
        <span className="inline-block h-2.5 w-2.5 rotate-45 border border-muted-foreground" />
        receiver-only mule (◇)
      </div>
    </div>
  );
}
