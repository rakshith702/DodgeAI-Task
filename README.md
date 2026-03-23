# SAP Order-to-Cash Graph Explorer

An AI-powered graph system that unifies SAP O2C data (orders, deliveries, billing, payments) into an interactive graph with a natural language query interface.

**Live Demo**: [your-deployment-url]  
**Repository**: [your-github-url]

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     React Frontend                       │
│  ┌─────────────────────┐  ┌────────────────────────┐    │
│  │   Graph Explorer    │  │    Chat Interface      │    │
│  │   (React Flow)      │  │  NL → SQL → Answer     │    │
│  └─────────────────────┘  └────────────────────────┘    │
└────────────────────┬────────────────────────────────────┘
                     │ REST API
┌────────────────────▼────────────────────────────────────┐
│                   FastAPI Backend                        │
│  ┌──────────────┐  ┌─────────────┐  ┌───────────────┐  │
│  │   SQLite DB  │  │  NetworkX   │  │ Claude Haiku  │  │
│  │  (11 tables) │  │   Graph     │  │  (NL → SQL)   │  │
│  └──────────────┘  └─────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

### Database Choice: SQLite + NetworkX (not a graph DB)

**Why not Neo4j?**
The dataset is small (~1,300 total records across 11 entity types). A dedicated graph database would add operational complexity (hosting, authentication, query language learning) without meaningful benefit at this scale.

**Dual-store approach:**
- **SQLite** handles structured queries (aggregations, filters, joins) — exactly what the NL→SQL pipeline needs. The LLM generates standard SQL which is universally understood and easy to validate.
- **NetworkX** (in-memory Python graph) handles graph traversal for the visualization API — neighbor expansion, path finding, degree queries. It loads from a pickle at startup in ~50ms.

This separation means each store does what it's best at.

---

### LLM Prompting Strategy

The system uses a **two-call pattern** per user query:

**Call 1 — SQL Generation (Claude Haiku)**
- System prompt contains the full schema (11 tables, all columns, FK relationships)
- Instructs Claude to respond ONLY with `{"sql": "...", "explanation": "..."}` JSON
- Strict guardrail instruction: if unrelated, respond with `GUARDRAIL:` prefix
- Model: `claude-haiku-4-5-20251001` — fast and cheap for structured output

**Call 2 — Result Summarization (Claude Haiku)**
- Passes the raw SQL rows + original question
- Asks for a concise natural language answer grounded in the data
- Keeps this call separate so SQL errors don't corrupt the natural language response

**Why not one call?**
Splitting generation from summarization makes errors easier to debug, allows showing the raw SQL to users, and keeps each call focused on a single task.

---

### Guardrails (Two Layers)

**Layer 1 — Regex pre-filter** (`guardrails.py` / `query_engine.py`):
Fast pattern matching before any LLM call. Blocks obvious off-topic requests (general knowledge, coding help, creative writing) in <1ms.

**Layer 2 — LLM instruction**:
The system prompt explicitly tells Claude to respond with `GUARDRAIL:` for anything unrelated to the dataset. This catches nuanced off-topic queries the regex misses.

Both layers return the same user-facing message:
> "This system is designed to answer questions related to the provided dataset only."

---

### Graph Model

Nodes (7 types):
- `BusinessPartner` — customers
- `SalesOrder` — order headers
- `Delivery` — outbound delivery headers
- `BillingDocument` — invoices
- `JournalEntry` — accounting entries
- `Payment` — accounts receivable payments
- `Product` — materials/SKUs

Edges (directed, representing the O2C flow):
```
BusinessPartner → SalesOrder        (PLACED_ORDER)
SalesOrder      → Delivery          (HAS_DELIVERY)
SalesOrder      → Product           (CONTAINS_PRODUCT)
Delivery        → BillingDocument   (HAS_BILLING)
BillingDocument → JournalEntry      (HAS_JOURNAL_ENTRY)
JournalEntry    → Payment           (CLEARED_BY)
```

The link from delivery to billing is derived from `billing_document_items.referenceSdDocument` pointing to `outbound_delivery_headers.deliveryDocument` — this is the key join that traces the O2C flow.

---

## Running Locally

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Copy .env and add your Anthropic API key
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY=sk-ant-...

# Ingest data and build graph (run once)
python ingest.py

# Start API server
uvicorn main:app --reload --port 8000
```

API will be at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm start
```

App will be at `http://localhost:3000`.

---

## Deployment

### Backend → Render.com (free tier)

1. Push `backend/` to a GitHub repo
2. Create a new **Web Service** on [render.com](https://render.com)
3. Connect your repo, set:
   - Build command: `pip install -r requirements.txt && python ingest.py`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add environment variable: `ANTHROPIC_API_KEY` = your key
5. Deploy — Render gives you a `https://xxx.onrender.com` URL

### Frontend → Vercel (free tier)

1. Push `frontend/` to GitHub
2. Import on [vercel.com](https://vercel.com)
3. Add environment variable: `REACT_APP_API_URL` = your Render backend URL
4. Deploy

---

## Example Queries

The system answers questions like:

| Question | What it does |
|---|---|
| Which products are associated with the highest number of billing documents? | Joins billing_document_items → products, groups by material |
| Trace the full flow of billing document 90504248 | Walks SO → Delivery → Billing → JE → Payment |
| Show sales orders delivered but not billed | LEFT JOIN delivery headers to billing items, filter NULLs |
| Which customers have the highest total payments? | Aggregates payments by customer, joins business_partners |
| List cancelled billing documents | Filters billing_document_cancellations where isCancelled=1 |

---

## Dataset Entities

| Entity | Records | Key Fields |
|---|---|---|
| sales_order_headers | 100 | salesOrder, soldToParty, totalNetAmount |
| sales_order_items | 167 | salesOrder, material, netAmount |
| billing_document_headers | 163 | billingDocument, soldToParty, totalNetAmount |
| billing_document_items | 245 | billingDocument, referenceSdDocument |
| outbound_delivery_headers | 86 | deliveryDocument, shippingPoint |
| outbound_delivery_items | 137 | deliveryDocument, referenceSdDocument (→ SO) |
| payments | 120 | accountingDocument, customer, amount |
| journal_entry_items | 123 | accountingDocument, referenceDocument (→ billing) |
| business_partners | 8 | businessPartner, businessPartnerFullName |
| products | 69 | product, productOldId, productGroup |
| billing_document_cancellations | 80 | billingDocument, billingDocumentIsCancelled |

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | React 18 + React Flow | React Flow handles large graph rendering efficiently with virtual nodes |
| Backend | FastAPI (Python) | Async, fast, automatic OpenAPI docs, great for data APIs |
| Database | SQLite | Zero infrastructure, fits dataset size, LLMs know SQL well |
| Graph lib | NetworkX | In-memory, Python-native, no infra needed at this scale |
| LLM | Claude Haiku 3.5 | Fast, cheap, excellent structured output, free tier available |
| Backend deploy | Render.com | Free tier, easy Python deploys, persistent disk for SQLite |
| Frontend deploy | Vercel | Free tier, instant React deploys |
