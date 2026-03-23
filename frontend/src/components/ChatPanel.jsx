import React, { useState, useRef, useEffect } from "react";
import { sendChat } from "../api";

const SUGGESTED = [
  "Which products are associated with the highest number of billing documents?",
  "Trace the full flow of billing document 90504248",
  "Show sales orders that have been delivered but not billed",
  "Which customers have the highest total payment amounts?",
  "List billing documents that have been cancelled",
  "Show me sales orders with incomplete delivery status",
];

function SqlBlock({ sql }) {
  const [show, setShow] = useState(false);
  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => setShow((s) => !s)}
        style={{
          background: "none",
          border: "1px solid #e2e8f0",
          borderRadius: 6,
          padding: "2px 10px",
          fontSize: 11,
          color: "#64748b",
          cursor: "pointer",
        }}
      >
        {show ? "Hide SQL ▲" : "Show SQL ▼"}
      </button>
      {show && (
        <pre
          style={{
            background: "#1e293b",
            color: "#e2e8f0",
            borderRadius: 8,
            padding: "10px 14px",
            fontSize: 11,
            overflowX: "auto",
            marginTop: 6,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {sql}
        </pre>
      )}
    </div>
  );
}

function DataTable({ rows }) {
  const [show, setShow] = useState(false);
  if (!rows || rows.length === 0) return null;
  const cols = Object.keys(rows[0]);
  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => setShow((s) => !s)}
        style={{
          background: "none",
          border: "1px solid #e2e8f0",
          borderRadius: 6,
          padding: "2px 10px",
          fontSize: 11,
          color: "#64748b",
          cursor: "pointer",
        }}
      >
        {show ? `Hide ${rows.length} rows ▲` : `Show ${rows.length} rows ▼`}
      </button>
      {show && (
        <div style={{ overflowX: "auto", marginTop: 6 }}>
          <table style={{ borderCollapse: "collapse", fontSize: 11, width: "100%" }}>
            <thead>
              <tr>
                {cols.map((c) => (
                  <th
                    key={c}
                    style={{
                      background: "#f1f5f9",
                      border: "1px solid #e2e8f0",
                      padding: "4px 8px",
                      textAlign: "left",
                      color: "#475569",
                      fontWeight: 600,
                    }}
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 20).map((row, i) => (
                <tr key={i} style={{ background: i % 2 === 0 ? "#fff" : "#f8fafc" }}>
                  {cols.map((c) => (
                    <td
                      key={c}
                      style={{ border: "1px solid #e2e8f0", padding: "3px 8px", color: "#334155" }}
                    >
                      {row[c] === null ? <em style={{ color: "#94a3b8" }}>null</em> : String(row[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > 20 && (
            <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>
              Showing 20 of {rows.length} rows
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ChatPanel({ selectedNode }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Hello! Ask me anything about the SAP Order-to-Cash dataset — orders, deliveries, billing documents, payments, customers, or products.",
      sql: null,
      rows: null,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // When a node is selected in the graph, pre-fill a query
  useEffect(() => {
    if (!selectedNode) return;
    const { nodeType, id, label } = selectedNode;
    if (!nodeType || !id) return;
    const q = `Tell me about ${nodeType} ${label || id}`;
    setInput(q);
  }, [selectedNode]);

  const submit = async (question) => {
    const q = question || input.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setLoading(true);
    try {
      const res = await sendChat(q);
      setMessages((m) => [
        ...m,
        { role: "assistant", text: res.answer, sql: res.sql, rows: res.rows, error: res.error },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: "Error: " + e.message, sql: null, rows: null },
      ]);
    }
    setLoading(false);
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "#fff",
        borderLeft: "1px solid #e2e8f0",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "14px 16px",
          borderBottom: "1px solid #e2e8f0",
          background: "#f8fafc",
        }}
      >
        <div style={{ fontSize: 15, fontWeight: 700, color: "#1e293b" }}>Query Assistant</div>
        <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
          Natural language → SQL → Answer
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 14px", display: "flex", flexDirection: "column", gap: 12 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: m.role === "user" ? "flex-end" : "flex-start" }}>
            <div
              style={{
                maxWidth: "88%",
                background: m.role === "user" ? "#3b82f6" : m.error ? "#fef2f2" : "#f1f5f9",
                color: m.role === "user" ? "#fff" : m.error ? "#dc2626" : "#1e293b",
                borderRadius: m.role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
                padding: "10px 14px",
                fontSize: 13,
                lineHeight: 1.6,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {m.text}
              {m.role === "assistant" && m.sql && <SqlBlock sql={m.sql} />}
              {m.role === "assistant" && m.rows && <DataTable rows={m.rows} />}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: "flex", alignItems: "flex-start" }}>
            <div
              style={{
                background: "#f1f5f9",
                borderRadius: "16px 16px 16px 4px",
                padding: "10px 14px",
                fontSize: 13,
                color: "#94a3b8",
              }}
            >
              Querying dataset…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggested queries */}
      {messages.length <= 1 && (
        <div style={{ padding: "0 14px 10px", display: "flex", flexDirection: "column", gap: 5 }}>
          <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 3 }}>Suggested queries:</div>
          {SUGGESTED.map((q, i) => (
            <button
              key={i}
              onClick={() => submit(q)}
              style={{
                background: "none",
                border: "1px solid #e2e8f0",
                borderRadius: 8,
                padding: "6px 10px",
                fontSize: 12,
                color: "#3b82f6",
                cursor: "pointer",
                textAlign: "left",
                transition: "background 0.1s",
              }}
              onMouseEnter={(e) => (e.target.style.background = "#eff6ff")}
              onMouseLeave={(e) => (e.target.style.background = "none")}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div
        style={{
          padding: "10px 14px",
          borderTop: "1px solid #e2e8f0",
          display: "flex",
          gap: 8,
          background: "#f8fafc",
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && submit()}
          placeholder="Ask about orders, deliveries, payments…"
          disabled={loading}
          style={{
            flex: 1,
            border: "1px solid #e2e8f0",
            borderRadius: 10,
            padding: "8px 12px",
            fontSize: 13,
            outline: "none",
            background: "#fff",
            color: "#1e293b",
          }}
        />
        <button
          onClick={() => submit()}
          disabled={loading || !input.trim()}
          style={{
            background: "#3b82f6",
            color: "#fff",
            border: "none",
            borderRadius: 10,
            padding: "8px 16px",
            fontSize: 13,
            fontWeight: 600,
            cursor: loading || !input.trim() ? "not-allowed" : "pointer",
            opacity: loading || !input.trim() ? 0.5 : 1,
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
