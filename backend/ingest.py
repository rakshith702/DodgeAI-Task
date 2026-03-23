"""
Ingest SAP O2C JSONL files into SQLite and build a NetworkX graph.
Run once: python ingest.py
"""
import json
import sqlite3
import glob
import os
import networkx as nx
import pickle
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = Path(__file__).parent / "o2c.db"
GRAPH_PATH = Path(__file__).parent / "o2c_graph.pkl"


def load_jsonl(folder: str) -> list[dict]:
    records = []
    pattern = str(DATA_DIR / folder / "part-*.jsonl")
    for fpath in glob.glob(pattern):
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def create_tables(conn: sqlite3.Connection):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS sales_order_headers (
        salesOrder TEXT PRIMARY KEY,
        salesOrderType TEXT,
        salesOrganization TEXT,
        soldToParty TEXT,
        creationDate TEXT,
        totalNetAmount REAL,
        overallDeliveryStatus TEXT,
        overallOrdReltdBillgStatus TEXT,
        transactionCurrency TEXT,
        requestedDeliveryDate TEXT,
        customerPaymentTerms TEXT
    );

    CREATE TABLE IF NOT EXISTS sales_order_items (
        salesOrder TEXT,
        salesOrderItem TEXT,
        material TEXT,
        requestedQuantity REAL,
        netAmount REAL,
        materialGroup TEXT,
        productionPlant TEXT,
        storageLocation TEXT,
        PRIMARY KEY (salesOrder, salesOrderItem)
    );

    CREATE TABLE IF NOT EXISTS billing_document_headers (
        billingDocument TEXT PRIMARY KEY,
        billingDocumentType TEXT,
        creationDate TEXT,
        billingDocumentDate TEXT,
        billingDocumentIsCancelled INTEGER,
        totalNetAmount REAL,
        transactionCurrency TEXT,
        companyCode TEXT,
        fiscalYear TEXT,
        accountingDocument TEXT,
        soldToParty TEXT
    );

    CREATE TABLE IF NOT EXISTS billing_document_items (
        billingDocument TEXT,
        billingDocumentItem TEXT,
        material TEXT,
        billingQuantity REAL,
        netAmount REAL,
        referenceSdDocument TEXT,
        referenceSdDocumentItem TEXT,
        PRIMARY KEY (billingDocument, billingDocumentItem)
    );

    CREATE TABLE IF NOT EXISTS outbound_delivery_headers (
        deliveryDocument TEXT PRIMARY KEY,
        creationDate TEXT,
        shippingPoint TEXT,
        overallGoodsMovementStatus TEXT,
        overallPickingStatus TEXT,
        actualGoodsMovementDate TEXT
    );

    CREATE TABLE IF NOT EXISTS outbound_delivery_items (
        deliveryDocument TEXT,
        deliveryDocumentItem TEXT,
        plant TEXT,
        referenceSdDocument TEXT,
        referenceSdDocumentItem TEXT,
        actualDeliveryQuantity REAL,
        storageLocation TEXT,
        PRIMARY KEY (deliveryDocument, deliveryDocumentItem)
    );

    CREATE TABLE IF NOT EXISTS payments (
        accountingDocument TEXT,
        accountingDocumentItem TEXT,
        companyCode TEXT,
        fiscalYear TEXT,
        clearingDate TEXT,
        clearingAccountingDocument TEXT,
        amountInTransactionCurrency REAL,
        transactionCurrency TEXT,
        customer TEXT,
        invoiceReference TEXT,
        postingDate TEXT,
        glAccount TEXT,
        PRIMARY KEY (accountingDocument, accountingDocumentItem)
    );

    CREATE TABLE IF NOT EXISTS journal_entry_items (
        accountingDocument TEXT,
        accountingDocumentItem TEXT,
        companyCode TEXT,
        fiscalYear TEXT,
        glAccount TEXT,
        referenceDocument TEXT,
        amountInTransactionCurrency REAL,
        postingDate TEXT,
        accountingDocumentType TEXT,
        customer TEXT,
        clearingDate TEXT,
        clearingAccountingDocument TEXT,
        PRIMARY KEY (accountingDocument, accountingDocumentItem)
    );

    CREATE TABLE IF NOT EXISTS business_partners (
        businessPartner TEXT PRIMARY KEY,
        customer TEXT,
        businessPartnerFullName TEXT,
        businessPartnerName TEXT,
        businessPartnerIsBlocked INTEGER,
        creationDate TEXT
    );

    CREATE TABLE IF NOT EXISTS products (
        product TEXT PRIMARY KEY,
        productType TEXT,
        productOldId TEXT,
        grossWeight REAL,
        weightUnit TEXT,
        productGroup TEXT,
        baseUnit TEXT,
        division TEXT
    );

    CREATE TABLE IF NOT EXISTS billing_document_cancellations (
        billingDocument TEXT PRIMARY KEY,
        billingDocumentType TEXT,
        creationDate TEXT,
        billingDocumentDate TEXT,
        billingDocumentIsCancelled INTEGER,
        totalNetAmount REAL,
        transactionCurrency TEXT,
        companyCode TEXT,
        fiscalYear TEXT,
        accountingDocument TEXT,
        soldToParty TEXT
    );
    """)
    conn.commit()


def ingest_all(conn: sqlite3.Connection):
    def safe(d, k):
        v = d.get(k)
        return None if v == "" else v

    # Sales order headers
    rows = load_jsonl("sales_order_headers")
    conn.executemany("""
        INSERT OR REPLACE INTO sales_order_headers VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, [(
        r["salesOrder"], r.get("salesOrderType"), r.get("salesOrganization"),
        r.get("soldToParty"), safe(r,"creationDate"),
        float(r["totalNetAmount"]) if r.get("totalNetAmount") else None,
        r.get("overallDeliveryStatus"), r.get("overallOrdReltdBillgStatus"),
        r.get("transactionCurrency"), safe(r,"requestedDeliveryDate"),
        r.get("customerPaymentTerms")
    ) for r in rows])

    # Sales order items
    rows = load_jsonl("sales_order_items")
    conn.executemany("""
        INSERT OR REPLACE INTO sales_order_items VALUES (?,?,?,?,?,?,?,?)
    """, [(
        r["salesOrder"], r["salesOrderItem"], r.get("material"),
        float(r["requestedQuantity"]) if r.get("requestedQuantity") else None,
        float(r["netAmount"]) if r.get("netAmount") else None,
        r.get("materialGroup"), r.get("productionPlant"), r.get("storageLocation")
    ) for r in rows])

    # Billing document headers
    rows = load_jsonl("billing_document_headers")
    conn.executemany("""
        INSERT OR REPLACE INTO billing_document_headers VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, [(
        r["billingDocument"], r.get("billingDocumentType"), safe(r,"creationDate"),
        safe(r,"billingDocumentDate"), int(r.get("billingDocumentIsCancelled", False)),
        float(r["totalNetAmount"]) if r.get("totalNetAmount") else None,
        r.get("transactionCurrency"), r.get("companyCode"), r.get("fiscalYear"),
        r.get("accountingDocument"), r.get("soldToParty")
    ) for r in rows])

    # Billing document items
    rows = load_jsonl("billing_document_items")
    conn.executemany("""
        INSERT OR REPLACE INTO billing_document_items VALUES (?,?,?,?,?,?,?)
    """, [(
        r["billingDocument"], r["billingDocumentItem"], r.get("material"),
        float(r["billingQuantity"]) if r.get("billingQuantity") else None,
        float(r["netAmount"]) if r.get("netAmount") else None,
        safe(r,"referenceSdDocument"), safe(r,"referenceSdDocumentItem")
    ) for r in rows])

    # Outbound delivery headers
    rows = load_jsonl("outbound_delivery_headers")
    conn.executemany("""
        INSERT OR REPLACE INTO outbound_delivery_headers VALUES (?,?,?,?,?,?)
    """, [(
        r["deliveryDocument"], safe(r,"creationDate"), r.get("shippingPoint"),
        r.get("overallGoodsMovementStatus"), r.get("overallPickingStatus"),
        safe(r,"actualGoodsMovementDate")
    ) for r in rows])

    # Outbound delivery items
    rows = load_jsonl("outbound_delivery_items")
    conn.executemany("""
        INSERT OR REPLACE INTO outbound_delivery_items VALUES (?,?,?,?,?,?,?)
    """, [(
        r["deliveryDocument"], r["deliveryDocumentItem"], r.get("plant"),
        safe(r,"referenceSdDocument"), safe(r,"referenceSdDocumentItem"),
        float(r["actualDeliveryQuantity"]) if r.get("actualDeliveryQuantity") else None,
        r.get("storageLocation")
    ) for r in rows])

    # Payments
    rows = load_jsonl("payments_accounts_receivable")
    conn.executemany("""
        INSERT OR REPLACE INTO payments VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, [(
        r["accountingDocument"], r["accountingDocumentItem"], r.get("companyCode"),
        r.get("fiscalYear"), safe(r,"clearingDate"), safe(r,"clearingAccountingDocument"),
        float(r["amountInTransactionCurrency"]) if r.get("amountInTransactionCurrency") else None,
        r.get("transactionCurrency"), r.get("customer"), safe(r,"invoiceReference"),
        safe(r,"postingDate"), r.get("glAccount")
    ) for r in rows])

    # Journal entry items
    rows = load_jsonl("journal_entry_items_accounts_receivable")
    conn.executemany("""
        INSERT OR REPLACE INTO journal_entry_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, [(
        r["accountingDocument"], r["accountingDocumentItem"], r.get("companyCode"),
        r.get("fiscalYear"), r.get("glAccount"), safe(r,"referenceDocument"),
        float(r["amountInTransactionCurrency"]) if r.get("amountInTransactionCurrency") else None,
        safe(r,"postingDate"), r.get("accountingDocumentType"), r.get("customer"),
        safe(r,"clearingDate"), safe(r,"clearingAccountingDocument")
    ) for r in rows])

    # Business partners
    rows = load_jsonl("business_partners")
    conn.executemany("""
        INSERT OR REPLACE INTO business_partners VALUES (?,?,?,?,?,?)
    """, [(
        r["businessPartner"], r.get("customer"), r.get("businessPartnerFullName"),
        r.get("businessPartnerName"), int(r.get("businessPartnerIsBlocked", False)),
        safe(r,"creationDate")
    ) for r in rows])

    # Products
    rows = load_jsonl("products")
    conn.executemany("""
        INSERT OR REPLACE INTO products VALUES (?,?,?,?,?,?,?,?)
    """, [(
        r["product"], r.get("productType"), r.get("productOldId"),
        float(r["grossWeight"]) if r.get("grossWeight") else None,
        r.get("weightUnit"), r.get("productGroup"), r.get("baseUnit"), r.get("division")
    ) for r in rows])

    # Billing document cancellations
    rows = load_jsonl("billing_document_cancellations")
    conn.executemany("""
        INSERT OR REPLACE INTO billing_document_cancellations VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, [(
        r["billingDocument"], r.get("billingDocumentType"), safe(r,"creationDate"),
        safe(r,"billingDocumentDate"), int(r.get("billingDocumentIsCancelled", False)),
        float(r["totalNetAmount"]) if r.get("totalNetAmount") else None,
        r.get("transactionCurrency"), r.get("companyCode"), r.get("fiscalYear"),
        r.get("accountingDocument"), r.get("soldToParty")
    ) for r in rows])

    conn.commit()
    print("All data ingested into SQLite.")


def build_graph(conn: sqlite3.Connection) -> nx.DiGraph:
    G = nx.DiGraph()

    # Add Sales Order nodes
    for row in conn.execute("SELECT salesOrder, soldToParty, totalNetAmount, creationDate, overallDeliveryStatus FROM sales_order_headers"):
        G.add_node(f"SO:{row[0]}", type="SalesOrder", id=row[0],
                   label=f"SO {row[0]}", soldToParty=row[1],
                   totalNetAmount=row[2], creationDate=row[3],
                   deliveryStatus=row[4])

    # Add Delivery nodes + edge from SO
    delivery_to_so = {}
    for row in conn.execute("SELECT DISTINCT deliveryDocument, referenceSdDocument FROM outbound_delivery_items WHERE referenceSdDocument IS NOT NULL"):
        delivery_to_so[row[0]] = row[1]

    for row in conn.execute("SELECT deliveryDocument, creationDate, shippingPoint, overallGoodsMovementStatus FROM outbound_delivery_headers"):
        G.add_node(f"DEL:{row[0]}", type="Delivery", id=row[0],
                   label=f"DEL {row[0]}", creationDate=row[1],
                   shippingPoint=row[2], goodsMovementStatus=row[3])
        so = delivery_to_so.get(row[0])
        if so and f"SO:{so}" in G:
            G.add_edge(f"SO:{so}", f"DEL:{row[0]}", relation="HAS_DELIVERY")

    # Add Billing Document nodes + edge from Delivery
    for row in conn.execute("SELECT billingDocument, soldToParty, totalNetAmount, billingDocumentDate, billingDocumentIsCancelled, accountingDocument FROM billing_document_headers"):
        G.add_node(f"BILL:{row[0]}", type="BillingDocument", id=row[0],
                   label=f"BILL {row[0]}", soldToParty=row[1],
                   totalNetAmount=row[2], billingDocumentDate=row[3],
                   isCancelled=bool(row[4]), accountingDocument=row[5])

    # Link Delivery -> Billing: billing_document_items.referenceSdDocument = deliveryDocument
    for row in conn.execute("SELECT DISTINCT billingDocument, referenceSdDocument FROM billing_document_items WHERE referenceSdDocument IS NOT NULL"):
        bill_id = f"BILL:{row[0]}"
        del_id = f"DEL:{row[1]}"
        if del_id in G and bill_id in G:
            G.add_edge(del_id, bill_id, relation="HAS_BILLING")

    # Add Journal Entry nodes + edge from Billing
    je_to_billing = {}
    for row in conn.execute("SELECT accountingDocument, referenceDocument FROM journal_entry_items WHERE referenceDocument IS NOT NULL"):
        je_to_billing[row[0]] = row[1]

    seen_je = set()
    for row in conn.execute("SELECT accountingDocument, postingDate, amountInTransactionCurrency, customer FROM journal_entry_items"):
        if row[0] not in seen_je:
            G.add_node(f"JE:{row[0]}", type="JournalEntry", id=row[0],
                       label=f"JE {row[0]}", postingDate=row[1],
                       amount=row[2], customer=row[3])
            seen_je.add(row[0])
            ref = je_to_billing.get(row[0])
            if ref and f"BILL:{ref}" in G:
                G.add_edge(f"BILL:{ref}", f"JE:{row[0]}", relation="HAS_JOURNAL_ENTRY")

    # Add Payment nodes + edge from Journal Entry
    for row in conn.execute("SELECT accountingDocument, accountingDocumentItem, clearingDate, amountInTransactionCurrency, customer, clearingAccountingDocument FROM payments"):
        node_id = f"PAY:{row[0]}:{row[1]}"
        G.add_node(node_id, type="Payment", id=row[0],
                   label=f"PAY {row[0]}", clearingDate=row[1],
                   amount=row[3], customer=row[4])
        # Link payment to the JE it clears
        clearing = row[5]
        if clearing and f"JE:{clearing}" in G:
            G.add_edge(f"JE:{clearing}", node_id, relation="CLEARED_BY")

    # Add Business Partner nodes + edges to SOs and Billings
    for row in conn.execute("SELECT businessPartner, businessPartnerFullName FROM business_partners"):
        G.add_node(f"BP:{row[0]}", type="BusinessPartner", id=row[0],
                   label=row[1] or f"BP {row[0]}", name=row[1])

    for row in conn.execute("SELECT salesOrder, soldToParty FROM sales_order_headers WHERE soldToParty IS NOT NULL"):
        if f"BP:{row[1]}" in G:
            G.add_edge(f"BP:{row[1]}", f"SO:{row[0]}", relation="PLACED_ORDER")

    # Add Product nodes + edges from SO items
    for row in conn.execute("SELECT product, productOldId, productGroup FROM products"):
        G.add_node(f"PROD:{row[0]}", type="Product", id=row[0],
                   label=row[1] or f"PROD {row[0]}", productGroup=row[2])

    for row in conn.execute("SELECT DISTINCT salesOrder, material FROM sales_order_items WHERE material IS NOT NULL"):
        prod_id = f"PROD:{row[1]}"
        if prod_id not in G:
            G.add_node(prod_id, type="Product", id=row[1], label=f"PROD {row[1]}")
        if f"SO:{row[0]}" in G:
            G.add_edge(f"SO:{row[0]}", prod_id, relation="CONTAINS_PRODUCT")

    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    ingest_all(conn)
    G = build_graph(conn)
    with open(GRAPH_PATH, "wb") as f:
        pickle.dump(G, f)
    print(f"Graph saved to {GRAPH_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
