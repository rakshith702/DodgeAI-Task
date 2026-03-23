"""
FastAPI backend for SAP O2C Graph Query System.
"""
import os
import pickle
import sqlite3
from pathlib import Path
from typing import Optional

import networkx as nx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from query_engine import ask

load_dotenv()

app = FastAPI(title="O2C Graph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE = Path(__file__).parent
DB_PATH = str(BASE / "o2c.db")
GRAPH_PATH = BASE / "o2c_graph.pkl"

# Load graph at startup
_graph: Optional[nx.DiGraph] = None


def get_graph() -> nx.DiGraph:
    global _graph
    if _graph is None:
        if not GRAPH_PATH.exists():
            raise HTTPException(500, "Graph not built. Run: python ingest.py")
        with open(GRAPH_PATH, "rb") as f:
            _graph = pickle.load(f)
    return _graph


# ── Models ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str


class ExpandRequest(BaseModel):
    node_id: str


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/graph/summary")
def graph_summary():
    """Return top-level graph stats and a sample of nodes for initial render."""
    G = get_graph()
    type_counts: dict[str, int] = {}
    for _, data in G.nodes(data=True):
        t = data.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Return a manageable subset: all BPs + SOs + first 20 of each other type
    sampled = []
    counts: dict[str, int] = {}
    limits = {"BusinessPartner": 999, "SalesOrder": 999, "Delivery": 20,
              "BillingDocument": 20, "JournalEntry": 10, "Payment": 10, "Product": 20}

    for node_id, data in G.nodes(data=True):
        t = data.get("type", "Unknown")
        limit = limits.get(t, 10)
        if counts.get(t, 0) < limit:
            sampled.append({"id": node_id, **data})
            counts[t] = counts.get(t, 0) + 1

    # Build edges only for sampled nodes
    sampled_ids = {n["id"] for n in sampled}
    edges = [
        {"source": u, "target": v, "relation": d.get("relation", "")}
        for u, v, d in G.edges(data=True)
        if u in sampled_ids and v in sampled_ids
    ]

    return {
        "stats": type_counts,
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "nodes": sampled,
        "edges": edges
    }


@app.post("/graph/expand")
def expand_node(req: ExpandRequest):
    """Return neighbors of a given node."""
    G = get_graph()
    if req.node_id not in G:
        raise HTTPException(404, f"Node {req.node_id} not found")

    neighbors = []
    edges = []

    for succ in G.successors(req.node_id):
        data = G.nodes[succ]
        neighbors.append({"id": succ, **data})
        edge_data = G.edges[req.node_id, succ]
        edges.append({"source": req.node_id, "target": succ, "relation": edge_data.get("relation", "")})

    for pred in G.predecessors(req.node_id):
        data = G.nodes[pred]
        neighbors.append({"id": pred, **data})
        edge_data = G.edges[pred, req.node_id]
        edges.append({"source": pred, "target": req.node_id, "relation": edge_data.get("relation", "")})

    return {
        "node": {"id": req.node_id, **G.nodes[req.node_id]},
        "neighbors": neighbors,
        "edges": edges
    }


@app.post("/chat")
def chat(req: ChatRequest):
    """Natural language query → SQL → answer."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(500, "GEMINI_API_KEY not set")

    result = ask(req.question, DB_PATH, api_key)
    return result


@app.get("/graph/node/{node_id}")
def get_node(node_id: str):
    """Get full metadata for a single node."""
    G = get_graph()
    node_id_decoded = node_id.replace("__COLON__", ":")
    if node_id_decoded not in G:
        raise HTTPException(404, f"Node not found")
    return {"id": node_id_decoded, **G.nodes[node_id_decoded]}
