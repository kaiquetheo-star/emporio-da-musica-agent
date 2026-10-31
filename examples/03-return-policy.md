# Applying the return policy (RAG)

> **Scenario.** Non-trivial scenario required by the case: the customer exercises the right of regret. The agent retrieves the store policy section (7-day window, original packaging, store-paid return shipping) and applies it, including the follow-up about the refund deadline (10 business days).

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

<sub>🔧 tool → `search_store_policies` · {"query": "prazo para devolução por arrependimento"}</sub>

**Zeca:** Olá! Tudo bem? Sim, a Empório da Música aceita devolução por arrependimento em até 7 dias corridos após o recebimento, desde que o produto esteja na embalagem original, sem sinais de uso, com todos os acessórios e manuais.

Para eu verificar o seu pedido e iniciar o processo, me passa o número do pedido, por favor?

**Cliente:** E o reembolso, em quanto tempo eu recebo?

<sub>🔧 tool → `search_store_policies` · {"query": "prazo para reembolso devolução arrependimento"}</sub>

**Zeca:** O reembolso é feito na mesma forma de pagamento original em até **10 dias úteis** após a devolução ser recebida e conferida.

Para eu verificar o seu pedido e iniciar a devolução, me passa o número do pedido, por favor?
