# Catalog query with price filter

> **Scenario.** Non-trivial scenario required by the case: the answer depends on live structured data. The customer asks for guitars (violões) under R$1000 — the agent must translate a natural language question into SQL, apply the price filter exactly and only list in-stock items, then answer a stock follow-up.

**Cliente:** Oi! Quais opções de violões vocês têm custando até R$1000?

<sub>🔧 tool → `run_sql_query` · {"sql": "SELECT * FROM categories"}</sub>

<sub>🔧 tool → `run_sql_query` · {"sql": "SELECT product_id, name, price_brl, active_discount_percent, effective_price_brl, stock_quantity, status FROM v_catalog WHERE category = 'Vio…</sub>

<sub>🔧 tool → `run_sql_query` · {"sql": "SELECT product_id, name, price_brl, active_discount_percent, effective_price_brl, stock_quantity, status FROM v_catalog WHERE effective_price…</sub>

**Zeca:** Oi! Temos várias opções de violões até R$1000. Aqui estão os mais populares:

**Nylon (clássico):**
- Yamaha C40 Nylon Natural — R$ 599,90
- Yamaha C70 Nylon Natural — R$ 849,00
- Tagima Memphis AC‑39 Nylon Natural — R$ 429,90
- Giannini GN‑15 Nylon Cedr Natural — R$ 689,00
- Rozini RC‑104 Nylon Estudante — R$ 459,90

**Aço (folk):**
- Tagima Dallas Tuner Aço Natural — R$ 749,00
- Yamaha F310 Aço Natural — R$ 699,90
- Giannini GF‑1R Aço Folk Sunburst — R$ 579,90
- Shelby SN‑100 Folk Aço Preto — R$ 549,00
- Tagima Woodstock Dreadnought Natural — R$ 899,00

Todos com estoque disponível (exceto o Giannini GF‑3D, que está sem unidades). Quer mais detalhes sobre algum modelo ou ajuda para escolher?

**Cliente:** Legal! E o mais barato deles tem em estoque?

<sub>🔧 tool → `run_sql_query` · {"sql": "SELECT name, stock_quantity, status FROM products WHERE name LIKE '%Memphis AC‑39%' OR name LIKE '%Tagima Memphis%';"}</sub>

**Zeca:** Sim! O Tagima Memphis AC‑39 Nylon Natural (R$ 429,90) tem 15 unidades em estoque e status ativo. Quer mais detalhes sobre esse modelo ou quer ver outras opções?
