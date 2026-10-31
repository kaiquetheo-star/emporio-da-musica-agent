# Real-time order status

> **Scenario.** The customer asks about a real order (#13). The agent queries the operational orders table, interprets the raw status ('pending') and adds context the customer actually cares about — no personal data beyond the requested order is disclosed.

**Cliente:** Oi, quero saber onde está meu pedido 13

<sub>🔧 tool → `run_sql_query` · {"sql": "SELECT * FROM v_order_overview WHERE order_id = 13"}</sub>

**Zeca:** Oi! Tudo bem? 👋

Consultando seu pedido **#13**:

- **Status:** Pendente
- **Data:** 12/03/2026
- **Produto:** Ohana BK-35E Barítono Elétrico Natural
- **Forma de pagamento:** PIX
- **Total:** R$ 1.899,00

Como o pedido ainda está pendente, não há código de rastreamento ou prazo de entrega definido ainda. Assim que ele for confirmado e enviado, te passamos o código de rastreamento.

Precisa de mais alguma coisa? Estou por aqui! 🎸
