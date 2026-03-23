import React, { useCallback, useEffect, useState, useRef } from "react";
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  addEdge,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { getGraphSummary, expandNode } from "../api";

// ── Color map by node type ────────────────────────────────────────────────
const TYPE_COLORS = {
  SalesOrder:      { bg: "#dbeafe", border: "#3b82f6", text: "#1e40af" },
  Delivery:        { bg: "#dcfce7", border: "#22c55e", text: "#166534" },
  BillingDocument: { bg: "#fef9c3", border: "#eab308", text: "#854d0e" },
  JournalEntry:    { bg: "#fce7f3", border: "#ec4899", text: "#9d174d" },
  Payment:         { bg: "#ede9fe", border: "#8b5cf6", text: "#4c1d95" },
  BusinessPartner: { bg: "#ffedd5", border: "#f97316", text: "#7c2d12" },
  Product:         { bg: "#f0fdf4", border: "#16a34a", text: "#14532d" },
};

// ── Custom node component ─────────────────────────────────────────────────
function EntityNode({ data, selected }) {
  const colors = TYPE_COLORS[data.nodeType] || { bg: "#f1f5f9", border: "#94a3b8", text: "#334155" };
  return (
    <div
      style={{
        background: colors.bg,
        border: `2px solid ${selected ? "#6366f1" : colors.border}`,
        borderRadius: 10,
        padding: "8px 14px",
        minWidth: 130,
        maxWidth: 180,
        cursor: "pointer",
        boxShadow: selected ? "0 0 0 3px rgba(99,102,241,0.3)" : "0 1px 4px rgba(0,0,0,0.08)",
        transition: "box-shadow 0.15s",
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: colors.border }} />
      <div style={{ fontSize: 10, fontWeight: 700, color: colors.border, textTransform: "uppercase", letterSpacing: 1, marginBottom: 3 }}>
        {data.nodeType}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: colors.text, lineHeight: 1.3, wordBreak: "break-word" }}>
        {data.label}
      </div>
      {data.amount && (
        <div style={{ fontSize: 11, color: "#64748b", marginTop: 3 }}>
          ₹{parseFloat(data.amount).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
        </div>
      )}
      {data.totalNetAmount && (
        <div style={{ fontSize: 11, color: "#64748b", marginTop: 3 }}>
          ₹{parseFloat(data.totalNetAmount).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
        </div>
      )}
      {data.expanded && (
        <div style={{ fontSize: 10, color: colors.border, marginTop: 4, fontStyle: "italic" }}>
          expanded ✓
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: colors.border }} />
    </div>
  );
}

const nodeTypes = { entity: EntityNode };

// ── Layout helper: simple layered layout by type ──────────────────────────
const TYPE_LAYERS = {
  BusinessPartner: 0,
  SalesOrder: 1,
  Delivery: 2,
  BillingDocument: 3,
  JournalEntry: 4,
  Payment: 5,
  Product: 6,
};

function autoLayout(nodes) {
  const grouped = {};
  for (const n of nodes) {
    const layer = TYPE_LAYERS[n.data.nodeType] ?? 7;
    if (!grouped[layer]) grouped[layer] = [];
    grouped[layer].push(n);
  }
  const GAP_X = 200, GAP_Y = 160, START_X = 60, START_Y = 60;
  const positioned = [];
  for (const [layer, group] of Object.entries(grouped)) {
    group.forEach((n, i) => {
      positioned.push({
        ...n,
        position: { x: START_X + i * GAP_X, y: START_Y + parseInt(layer) * GAP_Y },
      });
    });
  }
  return positioned;
}

// ── Main component ────────────────────────────────────────────────────────
export default function GraphView({ onNodeSelect }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const expandedRef = useRef(new Set());

  useEffect(() => {
    getGraphSummary().then((data) => {
      setStats({ total_nodes: data.total_nodes, total_edges: data.total_edges, ...data.stats });
      const initialNodes = data.nodes.map((n) => ({
        id: n.id,
        type: "entity",
        position: { x: 0, y: 0 },
        data: { ...n, nodeType: n.type, label: n.label || n.id },
      }));
      const laid = autoLayout(initialNodes);
      setNodes(laid);
      setEdges(
        data.edges.map((e, i) => ({
          id: `e${i}`,
          source: e.source,
          target: e.target,
          label: e.relation,
          animated: e.relation === "CLEARED_BY",
          style: { stroke: "#94a3b8", strokeWidth: 1.5 },
          labelStyle: { fontSize: 10, fill: "#64748b" },
          labelBgStyle: { fill: "#f8fafc", fillOpacity: 0.8 },
        }))
      );
      setLoading(false);
    });
  }, []);

  const onNodeClick = useCallback(
    async (_, node) => {
      onNodeSelect(node.data);
      if (expandedRef.current.has(node.id)) return;
      expandedRef.current.add(node.id);

      try {
        const data = await expandNode(node.id);
        const existingIds = new Set(nodes.map((n) => n.id));
        const newNodes = data.neighbors
          .filter((n) => !existingIds.has(n.id))
          .map((n) => ({
            id: n.id,
            type: "entity",
            position: {
              x: (node.position?.x || 0) + (Math.random() - 0.5) * 400,
              y: (node.position?.y || 0) + 160,
            },
            data: { ...n, nodeType: n.type, label: n.label || n.id },
          }));

        const existingEdgeIds = new Set(edges.map((e) => e.id));
        const newEdges = data.edges
          .filter((e) => !existingEdgeIds.has(`${e.source}-${e.target}`))
          .map((e) => ({
            id: `${e.source}-${e.target}`,
            source: e.source,
            target: e.target,
            label: e.relation,
            style: { stroke: "#94a3b8", strokeWidth: 1.5 },
            labelStyle: { fontSize: 10, fill: "#64748b" },
            labelBgStyle: { fill: "#f8fafc", fillOpacity: 0.8 },
          }));

        setNodes((ns) => {
          const updated = ns.map((n) =>
            n.id === node.id ? { ...n, data: { ...n.data, expanded: true } } : n
          );
          return [...updated, ...newNodes];
        });
        setEdges((es) => [...es, ...newEdges]);
      } catch (e) {
        console.error(e);
      }
    },
    [nodes, edges, onNodeSelect]
  );

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      {/* Stats bar */}
      {stats && (
        <div
          style={{
            position: "absolute",
            top: 12,
            left: 12,
            zIndex: 10,
            background: "rgba(255,255,255,0.93)",
            border: "1px solid #e2e8f0",
            borderRadius: 10,
            padding: "8px 14px",
            fontSize: 12,
            color: "#475569",
            boxShadow: "0 1px 6px rgba(0,0,0,0.07)",
          }}
        >
          <b style={{ color: "#1e293b" }}>O2C Graph</b>&nbsp;·&nbsp;
          {stats.total_nodes} nodes · {stats.total_edges} edges
          <div style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
            {Object.entries(TYPE_COLORS).map(([type, colors]) =>
              stats[type] ? (
                <span
                  key={type}
                  style={{
                    background: colors.bg,
                    border: `1px solid ${colors.border}`,
                    color: colors.text,
                    borderRadius: 6,
                    padding: "1px 7px",
                    fontSize: 11,
                  }}
                >
                  {type} ({stats[type]})
                </span>
              ) : null
            )}
          </div>
          <div style={{ marginTop: 5, color: "#94a3b8", fontSize: 11 }}>
            Click any node to expand its connections
          </div>
        </div>
      )}

      {loading && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "#f8fafc",
            zIndex: 20,
            fontSize: 14,
            color: "#64748b",
          }}
        >
          Loading graph…
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        maxZoom={2}
      >
        <Background color="#e2e8f0" gap={20} />
        <Controls />
        <MiniMap
          nodeColor={(n) => TYPE_COLORS[n.data?.nodeType]?.border || "#94a3b8"}
          style={{ border: "1px solid #e2e8f0", borderRadius: 8 }}
        />
      </ReactFlow>
    </div>
  );
}
