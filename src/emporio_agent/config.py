"""Central configuration: paths, LLM settings and runtime knobs."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Paths ───────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
POLICIES_PDF = DATA_DIR / "políticas_da_loja.pdf"
CONVERSATIONS_DIR = PROJECT_ROOT / "conversations"

CSV_FILES = {
    "categories": DATA_DIR / "desafio_tecnico_ai_eng - categories.csv",
    "customers": DATA_DIR / "desafio_tecnico_ai_eng - customers.csv",
    "products": DATA_DIR / "desafio_tecnico_ai_eng - products.csv",
    "promotions": DATA_DIR / "desafio_tecnico_ai_eng - promotions.csv",
    "orders": DATA_DIR / "desafio_tecnico_ai_eng - orders.csv",
    "order_items": DATA_DIR / "desafio_tecnico_ai_eng - order_items.csv",
}

# ── LLM provider (any OpenAI-compatible endpoint) ───────────────────────────
# Works out of the box with OpenRouter, Google Gemini (OpenAI-compatible
# endpoint), OpenAI, and self-hosted gateways such as LiteLLM/Ollama.
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "google/gemini-2.5-flash")

# ── Agent runtime ───────────────────────────────────────────────────────────
AGENT_MAX_TURNS = int(os.getenv("AGENT_MAX_TURNS", "6"))
