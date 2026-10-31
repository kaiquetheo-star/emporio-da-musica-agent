"""Generate the /examples interaction files from real agent runs.

Usage:
    python scripts/generate_examples.py

Requires a valid .env (see .env.example). Each conversation below is run
end-to-end through the real agent and written to examples/*.md, so the
shipped examples are always genuine transcripts — not hand-written fiction.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emporio_agent.agent import StoreAgent
from emporio_agent.ingest import load_store_db
from emporio_agent.policies import PolicyIndex

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"

CONVERSATIONS = [
    {
        "file": "01-catalog-query.md",
        "title": "Catalog query with price filter",
        "scenario": (
            "Non-trivial scenario required by the case: the answer depends "
            "on live structured data. The customer asks for guitars "
            "(violões) under R$1000 — the agent must translate a natural "
            "language question into SQL, apply the price filter exactly and "
            "only list in-stock items, then answer a stock follow-up."
        ),
        "turns": [
            "Oi! Quais opções de violões vocês têm custando até R$1000?",
            "Legal! E o mais barato deles tem em estoque?",
        ],
    },
    {
        "file": "02-order-status.md",
        "title": "Real-time order status",
        "scenario": (
            "The customer asks about a real order (#13). The agent queries "
            "the operational orders table, interprets the raw status "
            "('pending') and adds context the customer actually cares about "
            "— no personal data beyond the requested order is disclosed."
        ),
        "turns": [
            "Oi, quero saber onde está meu pedido 13",
        ],
    },
    {
        "file": "03-return-policy.md",
        "title": "Applying the return policy (RAG)",
        "scenario": (
            "Non-trivial scenario required by the case: the customer "
            "exercises the right of regret. The agent retrieves the store "
            "policy section (7-day window, original packaging, store-paid "
            "return shipping) and applies it, including the follow-up "
            "about the refund deadline (10 business days)."
        ),
        "turns": [
            "Me arrependi da minha compra, posso devolver meu pedido?",
            "E o reembolso, em quanto tempo eu recebo?",
        ],
    },
    {
        "file": "04-accessories-out-of-scope.md",
        "title": "Out-of-scope: accessories",
        "scenario": (
            "The store sells instruments only. The agent politely declines, "
            "redirects to partner accessory stores — without inventing any "
            "store name — and steers the conversation back to instruments."
        ),
        "turns": [
            "Vocês vendem cordas e palhetas de violão?",
        ],
    },
    {
        "file": "05-off-topic.md",
        "title": "Out-of-scope: unrelated topic",
        "scenario": (
            "A question completely unrelated to the store. The agent "
            "refuses kindly, restates what it can help with, and offers to "
            "continue the music-related conversation."
        ),
        "turns": [
            "Como conserto o pneu furado do meu carro?",
        ],
    },
]


def _fmt_tool(tc) -> str:
    args = json.dumps(tc.arguments, ensure_ascii=False)
    if len(args) > 150:
        args = args[:150] + "…"
    return f"`{tc.tool}` · {args}"


def run() -> None:
    db = load_store_db()
    agent = StoreAgent(db, PolicyIndex())
    EXAMPLES_DIR.mkdir(exist_ok=True)

    for conv in CONVERSATIONS:
        history: list[dict] = []
        blocks = [f"# {conv['title']}", "", f"> **Scenario.** {conv['scenario']}", ""]
        for turn in conv["turns"]:
            history.append({"role": "user", "content": turn})
            reply = agent.reply(history)
            history.append({"role": "assistant", "content": reply.text})
            blocks.append(f"**Cliente:** {turn}")
            blocks.append("")
            for tc in reply.tool_calls:
                blocks.append(f"<sub>🔧 tool → {_fmt_tool(tc)}</sub>")
                blocks.append("")
            blocks.append(f"**Zeca:** {reply.text}")
            blocks.append("")
        path = EXAMPLES_DIR / conv["file"]
        path.write_text("\n".join(blocks), encoding="utf-8")
        print(f"✓ {path.name}")


if __name__ == "__main__":
    run()
