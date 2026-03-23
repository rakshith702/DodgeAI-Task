import React from "react";

const TYPE_COLORS = {
  SalesOrder:      { bg: "#dbeafe", border: "#3b82f6", text: "#1e40af" },
  Delivery:        { bg: "#dcfce7", border: "#22c55e", text: "#166534" },
  BillingDocument: { bg: "#fef9c3", border: "#eab308", text: "#854d0e" },
  JournalEntry:    { bg: "#fce7f3", border: "#ec4899", text: "#9d174d" },
  Payment:         { bg: "#ede9fe", border: "#8b5cf6", text: "#4c1d95" },
  BusinessPartner: { bg: "#ffedd5", border: "#f97316", text: "#7c2d12" },
  Product:         { bg: "#f0fdf4", border: "#16a34a", text: "#14532d" },
};

const SKIP_KEYS = ["id", "type", "nodeType", "label", "expanded"];

function formatValue(key, val) {
  if (val === null || val === undefined || val === "") return <em style={{ color: "#94a3b8" }}>—</em>;
  if (key.toLowerCase().includes("amount") || key.toLowerCase().includes("netamount")) {
    const n = parseFloat(val);
    if (!isNaN(n)) return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
  }
  if (key.toLowerCase().includes("date") && typeof val === "string") {
    const d = new Date(val);
    if (!isNaN(d)) return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
  }
  if (typeof val === "boolean" || val === 0 || val === 1) {
    return val ? "Yes" : "No";
  }
  return String(val);
}

export default function NodeDetail({ node, onClose }) {
  if (!node) return null;
  const colors = TYPE_COLORS[node.nodeType] || { bg: "#f1f5f9", border: "#94a3b8", text: "#334155" };
  const fields = Object.entries(node).filter(([k]) => !SKIP_KEYS.includes(k));

  return (
    <div
      style={{
        position: "absolute",
        top: 60,
        right: 16,
        zIndex: 100,
        width: 260,
        background: "#fff",
        border: `1.5px solid ${colors.border}`,
        borderRadius: 12,
        boxShadow: "0 4px 24px rgba(0,0,0,0.10)",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          background: colors.bg,
          borderBottom: `1px solid ${colors.border}`,
          padding: "10px 14px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: colors.border, textTransform: "uppercase", letterSpacing: 1 }}>
            {node.nodeType}
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, color: colors.text, marginTop: 2, wordBreak: "break-word" }}>
            {node.label || node.id}
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: "none",
            border: "none",
            color: colors.text,
            fontSize: 16,
            cursor: "pointer",
            lineHeight: 1,
            padding: 0,
            marginLeft: 8,
          }}
        >
          ×
        </button>
      </div>

      {/* Fields */}
      <div style={{ padding: "10px 14px", maxHeight: 320, overflowY: "auto" }}>
        {fields.length === 0 && (
          <div style={{ fontSize: 12, color: "#94a3b8" }}>No additional metadata</div>
        )}
        {fields.map(([k, v]) => (
          <div key={k} style={{ marginBottom: 7 }}>
            <div style={{ fontSize: 10, color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
              {k.replace(/([A-Z])/g, " $1").trim()}
            </div>
            <div style={{ fontSize: 12, color: "#1e293b", wordBreak: "break-word" }}>
              {formatValue(k, v)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
