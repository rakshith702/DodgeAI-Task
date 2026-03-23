"""
Natural language → SQL query engine using Google Gemini API (free tier).
Includes guardrails to reject off-topic queries.
"""
import re
import json
import time
import sqlite3
import urllib.request
import urllib.error

SCHEMA = """
Tables in the SAP Order-to-Cash (O2C) SQLite database:

1. sales_order_headers
   - salesOrder TEXT PK
   - salesOrderType TEXT
   - salesOrganization TEXT
   - soldToParty TEXT             (FK → business_partners.businessPartner)
   - creationDate TEXT
   - totalNetAmount REAL
   - overallDeliveryStatus TEXT   ('A'=not started, 'B'=partial, 'C'=complete)
   - overallOrdReltdBillgStatus TEXT
   - transactionCurrency TEXT
   - requestedDeliveryDate TEXT
   - customerPaymentTerms TEXT

2. sales_order_items
   - salesOrder TEXT              (FK → sales_order_headers)
   - salesOrderItem TEXT
   - material TEXT                (FK → products.product)
   - requestedQuantity REAL
   - netAmount REAL
   - materialGroup TEXT
   - productionPlant TEXT
   - storageLocation TEXT

3. billing_document_headers
   - billingDocument TEXT PK
   - billingDocumentType TEXT     ('F2'=invoice, 'S1'=cancellation)
   - creationDate TEXT
   - billingDocumentDate TEXT
   - billingDocumentIsCancelled INTEGER (0/1)
   - totalNetAmount REAL
   - transactionCurrency TEXT
   - companyCode TEXT
   - fiscalYear TEXT
   - accountingDocument TEXT
   - soldToParty TEXT             (FK → business_partners.businessPartner)

4. billing_document_items
   - billingDocument TEXT         (FK → billing_document_headers)
   - billingDocumentItem TEXT
   - material TEXT                (FK → products.product)
   - billingQuantity REAL
   - netAmount REAL
   - referenceSdDocument TEXT     (FK → outbound_delivery_headers.deliveryDocument)
   - referenceSdDocumentItem TEXT

5. outbound_delivery_headers
   - deliveryDocument TEXT PK
   - creationDate TEXT
   - shippingPoint TEXT
   - overallGoodsMovementStatus TEXT  ('A'=not started, 'C'=complete)
   - overallPickingStatus TEXT
   - actualGoodsMovementDate TEXT

6. outbound_delivery_items
   - deliveryDocument TEXT        (FK → outbound_delivery_headers)
   - deliveryDocumentItem TEXT
   - plant TEXT
   - referenceSdDocument TEXT     (FK → sales_order_headers.salesOrder)
   - referenceSdDocumentItem TEXT
   - actualDeliveryQuantity REAL
   - storageLocation TEXT

7. payments
   - accountingDocument TEXT
   - accountingDocumentItem TEXT
   - companyCode TEXT
   - fiscalYear TEXT
   - clearingDate TEXT
   - clearingAccountingDocument TEXT
   - amountInTransactionCurrency REAL
   - transactionCurrency TEXT
   - customer TEXT                (FK → business_partners.businessPartner)
   - invoiceReference TEXT
   - postingDate TEXT
   - glAccount TEXT

8. journal_entry_items
   - accountingDocument TEXT
   - accountingDocumentItem TEXT
   - companyCode TEXT
   - fiscalYear TEXT
   - glAccount TEXT
   - referenceDocument TEXT       (FK → billing_document_headers.billingDocument)
   - amountInTransactionCurrency REAL
   - postingDate TEXT
   - accountingDocumentType TEXT
   - customer TEXT
   - clearingDate TEXT
   - clearingAccountingDocument TEXT

9. business_partners
   - businessPartner TEXT PK
   - customer TEXT
   - businessPartnerFullName TEXT
   - businessPartnerName TEXT
   - businessPartnerIsBlocked INTEGER (0/1)
   - creationDate TEXT

10. products
    - product TEXT PK
    - productType TEXT
    - productOldId TEXT
    - grossWeight REAL
    - weightUnit TEXT
    - productGroup TEXT
    - baseUnit TEXT
    - division TEXT

11. billing_document_cancellations
    - billingDocument TEXT PK
    - billingDocumentType TEXT
    - creationDate TEXT
    - billingDocumentDate TEXT
    - billingDocumentIsCancelled INTEGER
    - totalNetAmount REAL
    - transactionCurrency TEXT
    - companyCode TEXT
    - fiscalYear TEXT
    - accountingDocument TEXT
    - soldToParty TEXT

KEY RELATIONSHIPS:
- Sales order → delivery: outbound_delivery_items.referenceSdDocument = sales_order_headers.salesOrder
- Delivery → billing: billing_document_items.referenceSdDocument = outbound_delivery_headers.deliveryDocument
- Billing → journal entry: journal_entry_items.referenceDocument = billing_document_headers.billingDocument
- Journal entry → payment: payments.clearingAccountingDocument = journal_entry_items.accountingDocument
- Customer: sales_order_headers.soldToParty = business_partners.businessPartner
- Product: sales_order_items.material = products.product

FULL O2C FLOW JOIN PATTERN:
  sales_order_headers soh
  JOIN outbound_delivery_items odi ON odi.referenceSdDocument = soh.salesOrder
  JOIN outbound_delivery_headers odh ON odh.deliveryDocument = odi.deliveryDocument
  JOIN billing_document_items bdi ON bdi.referenceSdDocument = odh.deliveryDocument
  JOIN billing_document_headers bdh ON bdh.billingDocument = bdi.billingDocument
  JOIN journal_entry_items je ON je.referenceDocument = bdh.billingDocument
  LEFT JOIN payments pay ON pay.clearingAccountingDocument = je.accountingDocument
"""

SQL_SYSTEM_PROMPT = f"""You are a data query assistant for an SAP Order-to-Cash (O2C) dataset.
Your ONLY purpose is to answer questions about this dataset by generating SQLite SQL queries.

{SCHEMA}

RULES:
1. ONLY answer questions about the O2C dataset above.
2. If a question is unrelated to this dataset, respond EXACTLY with:
   GUARDRAIL: This system is designed to answer questions related to the provided dataset only.
3. Generate valid SQLite SQL. Always LIMIT results to 50 rows unless asked for more.
4. Respond with JSON in this exact format (no markdown, no code fences):
   {{"sql": "<your SQL query>", "explanation": "<brief explanation>"}}
5. If the question cannot be answered with SQL, respond with:
   {{"sql": null, "explanation": "<your answer in plain text>"}}
6. Never include markdown code fences in your response.
"""

SUMMARY_SYSTEM_PROMPT = """You are a data analyst assistant for an SAP Order-to-Cash system.
Answer based strictly on the data provided. Be concise and factual.
Do not make up any information not present in the data."""

OFF_TOPIC_PATTERNS = [
    r'\b(write|generate)\s+(me\s+)?(a\s+)?(story|poem|essay|haiku|song|code|script|function)\b',
    r'\bcreate\s+(a\s+)?(story|poem|essay|haiku|song|function|class|python|script)\b',
    r'\b(capital of|president of|prime minister|who is|what year|history of)\b',
    r'\b(python syntax|javascript|how to code|programming tutorial)\b',
    r'\b(weather forecast|sports score|breaking news|translate this|cooking recipe)\b',
    r'\btell me a (joke|story|poem|fact about(?!.*order|.*payment|.*invoice))\b',
]

# Models to try in order — if one is rate-limited, fall back to the next
GEMINI_MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-2.0-flash",
]


def quick_guardrail(query: str) -> bool:
    q = query.lower()
    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, q):
            return True
    return False


def run_query(sql: str, db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(sql)
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def gemini_call(prompt: str, system: str, api_key: str) -> str:
    """Call Gemini via REST with automatic model fallback on 429."""
    payload = json.dumps({
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024}
    }).encode()

    last_error = None
    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code == 429:
                # Rate limited — wait 3 seconds then try next model
                time.sleep(3)
                continue
            elif e.code == 404:
                # Model not found — try next
                continue
            else:
                raise
        except Exception as e:
            last_error = e
            continue

    raise Exception(f"All Gemini models failed. Last error: {last_error}")


def ask(user_question: str, db_path: str, api_key: str) -> dict:
    if quick_guardrail(user_question):
        return {
            "answer": "This system is designed to answer questions related to the provided dataset only.",
            "sql": None,
            "rows": None,
            "error": None
        }

    # Step 1: Generate SQL
    try:
        raw = gemini_call(user_question, SQL_SYSTEM_PROMPT, api_key)
    except Exception as e:
        return {"answer": f"LLM error: {str(e)}", "sql": None, "rows": None, "error": str(e)}

    if "GUARDRAIL:" in raw:
        return {
            "answer": "This system is designed to answer questions related to the provided dataset only.",
            "sql": None,
            "rows": None,
            "error": None
        }

    # Strip markdown fences if model added them
    raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()

    try:
        parsed = json.loads(raw)
        sql = parsed.get("sql")
        explanation = parsed.get("explanation", "")
    except Exception:
        return {"answer": raw, "sql": None, "rows": None, "error": None}

    if not sql:
        return {"answer": explanation, "sql": None, "rows": None, "error": None}

    # Step 2: Execute SQL
    try:
        rows = run_query(sql, db_path)
    except Exception as e:
        return {"answer": f"SQL error: {str(e)}\n\nGenerated SQL:\n{sql}", "sql": sql, "rows": None, "error": str(e)}

    # Step 3: Summarize results
    try:
        summary_prompt = f"""The user asked: "{user_question}"
SQL used: {sql}
Returned {len(rows)} rows:
{json.dumps(rows[:20], indent=2)}

Give a clear, concise natural language answer based strictly on this data.
If empty, say so clearly."""
        answer = gemini_call(summary_prompt, SUMMARY_SYSTEM_PROMPT, api_key)
    except Exception:
        answer = explanation + f"\n\nReturned {len(rows)} rows."

    return {"answer": answer, "sql": sql, "rows": rows, "error": None}
