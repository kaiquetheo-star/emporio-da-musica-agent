"""CSV ingestion into an in-memory SQLite database.

All operational CSVs (products, orders, customers, promotions, ...) are loaded
once at startup into a single in-memory SQLite database. The agent then reads
this structured data through a read-only SQL tool, which guarantees analytical
accuracy (exact filters, aggregations, joins) that would be unreliable with a
generative model working directly over raw CSV text.

Two convenience views are created on top of the raw tables:

* ``v_catalog``        — active catalog with category name and the best *active*
                         promotion applied (``effective_price_brl``).
* ``v_order_overview`` — orders joined with customer name and aggregated
                         product descriptions, so a single query answers
                         "where is my order #N?".
"""

from __future__ import annotations

import sqlite3

import pandas as pd

from .config import CSV_FILES

# Read-only role for the agent: data mutation is not part of the prototype.
_VIEWS_SQL = """
CREATE VIEW v_catalog AS
SELECT
    p.product_id,
    p.name,
    c.name AS category,
    p.price_brl,
    COALESCE(pr.discount_percent, 0) AS active_discount_percent,
    ROUND(p.price_brl * (1 - COALESCE(pr.discount_percent, 0) / 100.0), 2)
        AS effective_price_brl,
    p.stock_quantity,
    p.status
FROM products p
JOIN categories c ON c.category_id = p.category_id
LEFT JOIN (
    SELECT product_id, MAX(discount_percent) AS discount_percent
    FROM promotions
    WHERE is_active = 1
    GROUP BY product_id
) pr ON pr.product_id = p.product_id;

CREATE VIEW v_order_overview AS
SELECT
    o.order_id,
    cu.name AS customer,
    o.order_date,
    o.status,
    o.total_brl,
    o.payment_method,
    o.tracking_code,
    o.estimated_delivery,
    o.notes,
    GROUP_CONCAT(pi.product_name || ' x' || pi.quantity, '; ') AS items
FROM orders o
JOIN customers cu ON cu.customer_id = o.customer_id
JOIN (
    SELECT oi.order_id, oi.quantity, p.name AS product_name
    FROM order_items oi
    JOIN products p ON p.product_id = oi.product_id
) pi ON pi.order_id = o.order_id
GROUP BY o.order_id;
"""


def load_store_db() -> sqlite3.Connection:
    """Load every CSV into a fresh in-memory SQLite database and return it."""
    conn = sqlite3.connect(":memory:")
    for table, path in CSV_FILES.items():
        df = pd.read_csv(path, encoding="utf-8")
        # NaN notes/optional columns become NULL instead of the string "nan".
        df = df.where(pd.notna(df), None)
        df.to_sql(table, conn, index=False, if_exists="replace")
    conn.executescript(_VIEWS_SQL)
    return conn


def schema_doc(conn: sqlite3.Connection) -> str:
    """Human-readable schema documentation injected into the agent prompt."""
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "ORDER BY name"
        )
    ]
    lines = []
    for table in tables:
        cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
        col_doc = ", ".join(f"{c[1]} {c[2]}" for c in cols)
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        lines.append(f"- {table}({col_doc}) — {n} rows")
    lines.append(
        "- v_catalog(product_id, name, category, price_brl, "
        "active_discount_percent, effective_price_brl, stock_quantity, status) "
        "— active products with the best active promotion applied; "
        "status: active | discontinued | coming_soon"
    )
    lines.append(
        "- v_order_overview(order_id, customer, order_date, status, total_brl, "
        "payment_method, tracking_code, estimated_delivery, notes, items) "
        "— order status: pending | confirmed | shipped | delivered | cancelled"
    )
    return "\n".join(lines)
