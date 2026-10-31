"""The Empório da Música customer-service agent.

Architecture: native LLM *function calling* (no ReAct scaffold, no heavy
framework). The model decides when to consult data (SQL tool) and when to
consult the policy manual (BM25 tool); the host executes tools and loops the
results back until the model produces a final answer, bounded by a maximum
number of turns.

Why function calling over a ReAct loop: tool selection and argument schemas
are enforced by the provider's structured API instead of free-text "Thought/
Action" parsing, which removes a whole class of parsing failures and makes
tool use deterministic and auditable.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

from openai import OpenAI

from .config import AGENT_MAX_TURNS, LLM_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL
from .ingest import schema_doc
from .policies import PolicyIndex
from .tools import TOOLS_SPEC, execute_tool

SYSTEM_PROMPT_TEMPLATE = """Você é o Zeca, assistente virtual de atendimento \
da Empório da Música, loja de instrumentos musicais em Campo Grande/MS \
(fundada em 2008). Atende clientes pelo WhatsApp com o tom do manual da loja: \
informal, acolhedor e profissional — como um amigo que entende de música. \
Nunca robotizado, sempre em português do Brasil.

## Ferramentas de que você dispõe
1. run_sql_query — banco SQLite em memória com os dados da operação:
{schema}
   Use SEMPRE que o cliente perguntar sobre preço, disponibilidade, estoque, \
opções de produto, promoções ativas ou status de pedido. Regra absoluta do \
manual: nunca informe preço, estoque ou prazo sem antes consultar o sistema. \
Nunca invente produtos, preços ou números de pedido.
2. search_store_policies — busca no manual interno de políticas \
(devoluções, trocas, horários, pagamentos, frete, garantia, privacidade). \
Use SEMPRE que a pergunta envolver regras ou procedimentos da loja, em vez \
de responder de memória.

## Regras de atendimento
- Responda de forma curta e direta, em estilo de mensagem de WhatsApp \
(2 a 6 linhas). Liste produtos como "nome — preço" em linhas separadas.
- Preço promocional: quando houver desconto ativo, mostre o preço original, \
o percentual e o preço final (transparência é regra do manual).
- Produto sem estoque ou descontinuado: diga com transparência e sugira \
alternativas disponíveis (consulte o banco antes de sugerir).
- Status de pedido: o cliente precisa informar o número do pedido. Nunca \
dados pessoais de outros clientes; compartilhe apenas o que diz respeito ao \
pedido informado (privacidade/LGPD).
- Escopo: a loja vende EXCLUSIVAMENTE instrumentos musicais. Pedidos de \
acessórios (cordas, palhetas, cabos, cases, pedais, amplificadores) e \
qualquer assunto fora do universo da loja devem ser recusados com educação \
e, quando fizer sentido, redirecionados para "uma loja de acessórios \
parceira" — mas NUNCA invente nomes de lojas, sites ou contatos.
- Não invente informações que não estejam nas ferramentas. Se algo não \
estiver disponível nelas, seja honesto e ofereça encaminhar para a equipe \
humana (retorno em até 24h úteis).
- Cumprimente com simpatia na primeira mensagem e encerre confirmando se \
pode ajudar com mais alguma coisa.

## Dados fixos da loja (use quando pedirem, sem precisar de ferramenta)
- Endereço: Rua 14 de Maio, 3200 — Centro, Campo Grande/MS, CEP 79202-333
- Telefone/WhatsApp: (67) 3341-4444
- E-mail: contato@emporiodamusica.com.br
"""


@dataclass
class ToolCallRecord:
    """One executed tool call, kept for the UI and session transcripts."""

    tool: str
    arguments: dict
    result_preview: str
    ok: bool = True


@dataclass
class AgentReply:
    """Final answer of a turn plus the trace of tools used to build it."""

    text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


class StoreAgent:
    """Function-calling agent bound to one SQLite store and policy index."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        policy_index: PolicyIndex,
        model: str | None = None,
        max_turns: int = AGENT_MAX_TURNS,
    ) -> None:
        if not OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and "
                "configure your provider key."
            )
        self._client = OpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
        self._conn = conn
        self._policies = policy_index
        self._model = model or LLM_MODEL
        self._max_turns = max_turns
        self._system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            schema=schema_doc(conn)
        )

    def reply(self, history: list[dict]) -> AgentReply:
        """Answer the last user message, running tools as needed.

        ``history`` is a list of OpenAI-style chat messages (without the
        system prompt, which is injected here); it is not mutated.
        """
        messages = (
            [{"role": "system", "content": self._system_prompt}, *history]
        )
        trace: list[ToolCallRecord] = []

        for _ in range(self._max_turns):
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=TOOLS_SPEC,
                tool_choice="auto",
                temperature=0.2,
            )
            choice = response.choices[0]
            assistant_msg = choice.message

            if assistant_msg.tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_msg.content or "",
                        "tool_calls": [
                            tc.model_dump(exclude_none=True)
                            for tc in assistant_msg.tool_calls
                        ],
                    }
                )
                for call in assistant_msg.tool_calls:
                    result = self._execute(call)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": result,
                        }
                    )
                continue

            return AgentReply(
                text=(assistant_msg.content or "").strip(), tool_calls=trace
            )

        # Turn budget exhausted — degrade gracefully instead of rambling.
        return AgentReply(
            text=(
                "Deixa eu confirmar esse detalhe com a equipe da loja e eu "
                "te retorno rapidinho, tá bom? 😊"
            ),
            tool_calls=trace,
        )

    def _execute(self, call) -> str:
        try:
            arguments = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}
        result = execute_tool(
            call.function.name, arguments, self._conn, self._policies
        )
        trace_preview = result if len(result) <= 220 else result[:220] + "…"
        trace.append(
            ToolCallRecord(
                tool=call.function.name,
                arguments=arguments,
                result_preview=trace_preview,
                ok="error" not in result[:60].lower(),
            )
        )
        return result
