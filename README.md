# Empório da Música — AI Customer Service Agent

A functional prototype of a generative-AI customer service agent for
**Empório da Música**, a fictional musical instrument store in Campo
Grande/MS (Artefact technical challenge — AI Engineer, 2026).

The agent — "Zeca" — chats with customers in Brazilian Portuguese over a
WhatsApp-style CLI. It answers **catalog questions (prices, stock, product
options) from live structured data**, applies **store policies** (returns,
payment rules, hours, shipping, warranty) retrieved from the internal manual,
and **politely refuses out-of-scope requests**.

```
Você › Quais opções de violões vocês têm até R$1000?
  🔧 run_sql_query {'sql': "SELECT name, effective_price_brl, stock_quantity FROM v_catalog
     WHERE category='Violões' AND effective_price_brl <= 1000 ..."}
┌─────────────────────────────────────────────────────────────────────────────
│ Zeca ›
│ Boa! Temos essas opções de violões até R$1000:
│ Tagima Memphis AC-39 — R$429,90
│ Rozini RC-104 Estudante — R$459,90
│ Shelby SN-100 Folk — R$549,00
│ Giannini GF-1R Folk — R$579,90
│ Yamaha C40 — R$599,90
│ Quer que eu detalhe algum deles?
└─────────────────────────────────────────────────────────────────────────────
```

## Architecture

```
                 ┌──────────────────────────────────────────────┐
 user message ──▶│                 StoreAgent                   │
                │  (native function-calling loop, ≤ N turns)   │
                 │                                              │
                 │   system prompt: persona + rules + schema    │
                 └───────┬───────────────────────┬──────────────┘
                         │ tool_call              │ tool_call
                 ┌───────▼─────────┐     ┌────────▼─────────────┐
                 │ run_sql_query   │     │ search_store_policies│
                 │ (read-only SQL) │     │ (BM25 over PDF)      │
                 └───────┬─────────┘     └────────┬─────────────┘
                 ┌───────▼─────────┐     ┌────────▼─────────────┐
                 │ SQLite (memory) │     │ Policy index (26     │
                 │ 6 CSVs + 2 views│     │ section chunks)      │
                 └─────────────────┘     └─────────────────────┘
```

**Two knowledge sources, two tools.** Operational data (products, stock,
orders, promotions) is *structured* — questions about it become **SQL**.
Store policies are *procedural prose* — questions about them go through
**keyword retrieval** over the manual. The LLM itself never decides prices or
policy terms; it orchestrates tools and phrases the answer.

### Agent approach — native function calling (no ReAct, no framework)

I used the provider's **native tool-calling API** with a thin orchestration
loop (~90 lines), instead of a ReAct scaffold or a heavyweight agent
framework:

* Tool selection and arguments are **schema-validated by the provider**,
  not parsed from free text — this removes the classic ReAct failure mode
  (malformed "Thought/Action" strings) and makes every tool use auditable.
* No framework lock-in: the whole agent is one class over the
  OpenAI-compatible SDK. Anything (LangChain, memory backends, streaming)
  can be bolted on later without rewriting the core.

### LLM provider — OpenAI-compatible layer (provider-agnostic)

The agent talks to **any OpenAI-compatible endpoint** via three env vars.
Tested with **Google Gemini 2.5 Flash** (excellent Portuguese quality and
tool calling, generous free tier) via Gemini's OpenAI-compatible endpoint;
switching to OpenRouter, OpenAI, Anthropic or a local gateway (Ollama,
LiteLLM) is a one-line `.env` change:

```env
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_API_KEY=your-key
LLM_MODEL=gemini-2.5-flash
```

### Data handling — CSVs → in-memory SQLite (agentic SQL)

At startup, `pandas` loads all six CSVs into an **in-memory SQLite** database
with two convenience views:

* `v_catalog` — active products joined with category and the best **active**
  promotion (`effective_price_brl`), so promotion rules (manual §6.2) are
  applied by the data layer, not by the model's arithmetic;
* `v_order_overview` — orders + customer + aggregated items, so "where is my
  order #13?" is a single query.

Why SQL over feeding CSVs to the model: filters, price ranges, joins and
counts must be **exact** (a wrong price is legally sensitive — manual §7.1:
*"never give price/stock/lead-time info without checking the system"*). SQL
gives determinism, and the schema is documented in the system prompt.

**Security:** the SQL tool is defense-in-depth — single-statement validation,
`SELECT`-only, keyword denylist (`INSERT/UPDATE/DROP/ATTACH/PRAGMA/…`),
forced `LIMIT`, row caps. The database is ephemeral, but the tool is written
as if it faced a hostile caller — the pattern transfers to production.

### Policy retrieval — chunked PDF + BM25 (deliberately, not embeddings)

The 8-page manual is chunked **by section** (26 chunks, headings kept with
their content) and indexed with **BM25** using a Portuguese snowball stemmer
and accent normalization — so *"me arrependi da compra"* correctly retrieves
*"Direito de Arrependimento"*.

Why not embeddings + a vector DB: for a corpus this small, lexical search
with stemming is deterministic, instant to start, has **zero model download**
(a multilingual MiniLM would add ~500 MB) and is trivially inspectable. The
system prompt still routes all policy questions through the tool, so the
retrieval layer can be swapped for dense embeddings + pgvector without
touching the agent (see *Limitations*).

### Prompt strategy

The system prompt encodes, in Portuguese (the working language):

* **Persona:** Zeca — informal-but-professional store assistant, per the
  manual's own tone-of-voice rules (§7.1), WhatsApp-style short answers;
* **Grounding rules:** *never* state prices/stock/lead times without calling
  the SQL tool; *never* state policy terms without the retrieval tool;
* **Behavioral rules from the manual:** show original price + discount %,
  offer alternatives for out-of-stock items, refuse accessory requests
  (the store sells instruments only — §1), never promise expired promotions
  (§7.3), escalate to the human team when tools have no answer (24h SLA);
* **Privacy (LGPD, §9):** order data requires the order number; no personal
  data of other customers is ever revealed;
* **Schema documentation** for the SQL tool is injected at build time.

## Setup & execution

Requirements: Python 3.11+.

```bash
git clone https://github.com/kaiquetheo-star/emporio-da-musica-agent
cd emporio-da-musica-agent

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env             # then edit .env with your key + model
python main.py
```

The CLI prints which tool the agent used for each answer. Commands: `/reset`
(clear conversation), `/sair` (exit). Sessions are auto-saved as JSONL under
`conversations/` (gitignored).

A **fictitious order number** is useful for testing order-status flows:
try `13`, `8` or `17` (pending / shipped / cancelled — see
`data/desafio_tecnico_ai_eng - orders.csv`).

## Project structure

```
main.py                     # entry point (python main.py)
src/emporio_agent/
  config.py                 # env vars, paths, runtime knobs
  ingest.py                 # CSVs → in-memory SQLite + views
  policies.py               # PDF → section chunks → BM25 index
  tools.py                  # tool schemas, SQL guardrails, dispatch
  agent.py                  # persona/system prompt + tool-calling loop
  session.py                # chat history + JSONL persistence
  cli.py                    # Typer/Rich interactive chat
data/                       # store CSVs + policy manual PDF (given)
examples/                   # 5 recorded interactions (see below)
```

## Interaction examples

Recorded in [`examples/`](examples/) — five scenarios, including the
non-trivial ones required by the case (real-time data query and policy
application):

| # | Scenario | Shows |
|---|----------|-------|
| 1 | Catalog query: "violões até R$1000" | SQL tool, price range, alternatives |
| 2 | Order status: "onde está meu pedido #13?" | real-time order data + status semantics |
| 3 | Regret: "me arrependi, posso devolver?" | policy retrieval (7-day rule) applied |
| 4 | Accessories (out of scope): "vocês vendem cordas?" | scope guardrail, polite redirect |
| 5 | Off-topic: car tire repair | refusal, back on rails |

## AI workflow & code assistants

This project was built **AI-first**, with coding assistants as pair
programmers rather than autocompleters:

* **OpenCode (GLM agent)** — the primary driver: project scaffolding, the
  ingestion/retrieval/agent layers, SQL-guardrail attack tests, and this
  README itself. Used as a long agentic session with incremental commits.
* **Human role (mine)** — architecture decisions (function calling vs ReAct,
  SQL vs direct CSV, BM25 vs embeddings), prompt/persona design grounded in
  the actual manual sections, security review of the tool layer, and
  end-to-end validation of every example conversation.

The commit history reflects this workflow: each layer landed separately
(data → retrieval → tools/agent → CLI) with tests run before the LLM was
ever plugged in — the same discipline I'd apply without assistants, just
faster.

## Assumptions (documented per the case instructions)

* The manual lists two phone numbers (cover: (67) 3341-4444; §7:
  (67) 3321-4500). The agent uses the cover/contact-table number.
* Order lookup requires the **order number** (the CSV has no auth layer for
  a prototype; name/phone matching would leak third-party personal data).
* Promotion transparency (§6.2) is enforced via the `v_catalog` view, which
  exposes original and effective price.
* Conversations are single-session; there is no cross-session memory.

## Known limitations & future improvements

* **Ephemeral persistence** — SQLite and the BM25 index live in memory and
  are rebuilt at startup (~1 s). Production: managed Postgres (+`pgvector`
  for the policy index), ingestion as a job rather than at boot.
* **Lexical retrieval** — BM25 with stemming covers this manual well, but
  truly paraphrased questions would benefit from multilingual dense
  embeddings hybrid-ranked with BM25.
* **No streaming** — answers render only after tools finish; a UI would
  want token streaming.
* **No conversation memory across sessions** — `session.py` persists JSONL
  transcripts for reproducibility, but a returning customer starts fresh.
  Production: Redis-backed session store keyed by customer phone.
* **Single language** — persona and prompts are PT-BR only; the prompt is
  data-driven enough to localize.
* **No evaluation harness** — with more time I'd add a small golden-set of
  Q→expected-tool/assertion cases (e.g. with `pytest`) to catch regressions
  in tool selection.
