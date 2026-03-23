import React, { useState } from "react";
import GraphView from "./components/GraphView";
import ChatPanel from "./components/ChatPanel";
import NodeDetail from "./components/NodeDetail";

export default function App() {
  const [selectedNode, setSelectedNode] = useState(null);
  const [chatWidth, setChatWidth] = useState(380);
  const [dragging, setDragging] = useState(false);

  const onMouseDown = (e) => {
    setDragging(true);
    e.preventDefault();
  };

  const onMouseMove = (e) => {
    if (!dragging) return;
    const newWidth = window.innerWidth - e.clientX;
    setChatWidth(Math.max(280, Math.min(600, newWidth)));
  };

  const onMouseUp = () => setDragging(false);

  return (
    <div
      style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#f8fafc", userSelect: dragging ? "none" : "auto" }}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
    >
      {/* Header */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 48,
          background: "#1e293b",
          zIndex: 200,
          display: "flex",
          alignItems: "center",
          padding: "0 20px",
          gap: 12,
          boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
        }}
      >
        <div style={{ fontSize: 16, fontWeight: 700, color: "#f1f5f9" }}>
          SAP O2C Graph Explorer
        </div>
        <div
          style={{
            fontSize: 11,
            color: "#64748b",
            background: "#0f172a",
            borderRadius: 6,
            padding: "2px 8px",
          }}
        >
          Order-to-Cash · AI-Powered
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: 11, color: "#475569" }}>
          Click nodes to explore · Chat to query data
        </div>
      </div>

      {/* Graph panel */}
      <div
        style={{
          flex: 1,
          marginTop: 48,
          position: "relative",
          overflow: "hidden",
        }}
      >
        <GraphView onNodeSelect={setSelectedNode} />
        {selectedNode && (
          <NodeDetail node={selectedNode} onClose={() => setSelectedNode(null)} />
        )}
      </div>

      {/* Drag handle */}
      <div
        onMouseDown={onMouseDown}
        style={{
          width: 5,
          marginTop: 48,
          background: dragging ? "#3b82f6" : "#e2e8f0",
          cursor: "col-resize",
          transition: "background 0.15s",
          flexShrink: 0,
        }}
      />

      {/* Chat panel */}
      <div
        style={{
          width: chatWidth,
          marginTop: 48,
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <ChatPanel selectedNode={selectedNode} />
      </div>
    </div>
  );
}
