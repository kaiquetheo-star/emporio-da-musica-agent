"""Agent tools: JSON schemas, SQL guardrails and execution dispatch.

The agent exposes exactly two tools:

* ``run_sql_query``          — read-only SELECTs against the in-memory SQLite
                               built from the operational CSVs (products,
                               stock, prices, orders, promotions).
* ``search_store_policies``  — BM25 semantic-ish lookup over the store policy
                               manual (returns, exchanges, hours, payments,
                               shipping, warranty, privacy).

The SQL tool is defense-in-depth: statement validation (single SELECT only),
a forbidden-keyword denylist, forced row cap and a busy timeout. Even though
the database is ephemeral and in-memory, the tool is written as if it faced
a hostile caller — the pattern transfers to production stores.
"""

from __future__ import annotations

import json
import re
import sqlite3

from .ingest import schema_doc
from .policies import PolicyIndex

MAX_ROWS = 50

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|"
    r"detach|pragma|reindex|vacuum|grant|revoke)\b",
    re.IGNORECASE,
)
_SEMICOLON_OUTSIDE_STRINGS = re.compile(r";(?=(?:[^']*'[^']*')*[^']*$)")


def _validate_select(sql: str) -> str:
    """Raise ValueError unless ``sql`` is a single, read-only SELECT."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise ValueError("Empty SQL query.")
    if _SEMICOLON_OUTSIDE_STRINGS.search(stripped):
        raise ValueError("Only a single SQL statement is allowed.")
    if not re.match(r"^select\b", stripped, re.IGNORECASE):
        raise ValueError("Only SELECT statements are allowed.")
    if _FORBIDDEN.search(stripped):
        raise ValueError("Query contains a forbidden keyword.")
    # Force a row cap when the model forgot it (cheap safety net).
    if not re.search(r"\blimit\b", stripped, re.IGNORECASE):
        stripped = f"{stripped} LIMIT {MAX_ROWS}"
    return stripped


def run_sql_query(sql: str, conn: sqlite3.Connection) -> str:
    """Execute a validated read-only query; return rows as JSON."""
    try:
        safe_sql = _validate_select(sql)
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    try:
        cur = conn.execute(safe_sql)
        columns = [d[0] for d in cur.description]
        rows = [
            [None if v is None else (float(v) if isinstance(v, float) else v)
             for v in row]
            for row in cur.fetchmany(MAX_ROWS)
        ]
        return json.dumps(
            {"columns": columns, "rows": rows, "row_count": len(rows)},
            ensure_ascii=False,
            default=str,
        )
    except sqlite3.Error as exc:
        return json.dumps(
            {"error": f"SQLite error: {exc}"}, ensure_ascii=False
        )


def search_store_policies(query: str, index: PolicyIndex, k: int = 4) -> str:
    """Return the most relevant store-policy excerpts for a natural query."""
    hits = index.search(query, k=k)
    if not hits:
        return json.dumps(
            {"results": [],
             "hint": "No policy section matched. Ask the customer for "
                     "details or escalate to the human team."},
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "results": [
                {
                    "section": hit.section,
                    "page": hit.page,
                    "text": hit.text,
                }
                for hit in hits
            ]
        },
        ensure_ascii=False,
    )


TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "run_sql_query",
            "description": (
                "Run a read-only SQL SELECT against the store's operational "
                "database (SQLite, in memory) to answer questions about "
                "products, prices, stock, active promotions, customers, "
                "orders and order status. Use it whenever the customer asks "
                "about availability, price, catalog options or their order. "
                "Prefer the convenience views v_catalog and v_order_overview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": (
                            "A single SELECT statement. Always include an "
                            "appropriate WHERE clause and LIMIT."
                        ),
                    }
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_store_policies",
            "description": (
                "Search the internal store policy manual (returns/refunds, "
                "exchanges, opening hours, payment methods and installments, "
                "shipping and delivery, tracking, promotions rules, "
                "warranty, privacy). Use it for any question about rules "
                "and procedures instead of answering from memory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query in Portuguese, e.g. 'prazo para "
                            "devolução por arrependimento'."
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    },
]


def execute_tool(
    name: str,
    arguments: dict,
    conn: sqlite3.Connection,
    policy_index: PolicyIndex,
) -> str:
    """Dispatch a tool call requested by the LLM."""
    if name == "run_sql_query":
        return run_sql_query(arguments["sql"], conn)
    if name == "search_store_policies":
        return search_store_policies(arguments["query"], policy_index)
    return json.dumps({"error": f"Unknown tool: {name}"})


def tool_prompt_doc(conn: sqlite3.Connection) -> str:
    """Schema documentation block for the system prompt."""
    return schema_doc(conn)
