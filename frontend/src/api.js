const BASE = import.meta.env.VITE_API_URL || "";

export async function getGraphSummary() {
  const res = await fetch(`${BASE}/graph/summary`);
  if (!res.ok) throw new Error("Failed to load graph");
  return res.json();
}

export async function expandNode(nodeId) {
  const res = await fetch(`${BASE}/graph/expand`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ node_id: nodeId }),
  });
  if (!res.ok) throw new Error("Failed to expand node");
  return res.json();
}

export async function sendChat(question) {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error("Chat request failed");
  return res.json();
}
