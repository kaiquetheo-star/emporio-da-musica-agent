"""Rich CLI chat for the Empório da Música agent.

Usage:
    python main.py
    python main.py --model google/gemini-2.5-flash
"""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from .agent import StoreAgent
from .ingest import load_store_db
from .policies import PolicyIndex
from .session import ChatSession

app = typer.Typer(add_completion=False, no_args_is_help=False)
console = Console()

BANNER = r"""[bold cyan]♬  Empório da Música[/] — agente de atendimento
[dim]Zeca, o assistente virtual da loja. Sua música começa aqui.[/]
[dim]Comandos: /reset limpa a conversa · /sair encerra[/]"""

HELP_OPTIONS = ("--model",)


@app.command()
def chat(
    model: str = typer.Option(
        None, help="Override the LLM model id from .env (provider-specific)."
    ),
    save: bool = typer.Option(
        True, "--save/--no-save", help="Persist the session transcript."
    ),
) -> None:
    """Start an interactive customer chat session."""
    console.print(Rule())
    console.print(BANNER)
    console.print(Rule())

    console.print("[dim]Carregando catálogo, pedidos e políticas...[/]")
    db = load_store_db()
    policies = PolicyIndex()
    try:
        agent = StoreAgent(db, policies, model=model)
    except RuntimeError as exc:
        console.print(f"[red]✗ {exc}[/]")
        raise typer.Exit(code=1) from exc
    product_count = db.execute(
        "SELECT COUNT(*) FROM v_catalog"
    ).fetchone()[0]
    console.print(
        f"[green]✓[/] Loja carregada: {product_count} produtos ativos · "
        f"{len(policies.chunks)} seções de políticas indexadas\n"
    )

    session = ChatSession()
    while True:
        try:
            user_input = console.input("[bold green]Você ›[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Até mais! 🎵[/]")
            break

        if not user_input:
            continue
        low = user_input.lower()
        if low in {"/sair", "/exit", "/quit"}:
            console.print("[dim]Até mais! 🎵[/]")
            break
        if low == "/reset":
            session.reset()
            console.print("[yellow]Conversa reiniciada.[/]\n")
            continue

        session.add_user(user_input)
        with console.status("[dim]Zeca está digitando...[/]"):
            reply = agent.reply(session.messages)

        for tc in reply.tool_calls:
            console.print(
                f"  [magenta]🔧 {tc.tool}[/] "
                f"[dim]{_compact(tc.arguments)}[/]"
            )
        console.print(
            Panel(
                Text(reply.text),
                title="[bold cyan]Zeca ›[/]",
                title_align="left",
                border_style="cyan",
            )
        )
        session.add_assistant(
            reply.text,
            tool_calls=[
                {"tool": tc.tool, "arguments": tc.arguments}
                for tc in reply.tool_calls
            ],
        )
        console.print()

    if save and session.events:
        path = session.save()
        console.print(f"[dim]Conversa salva em: {path}[/]")


def _compact(args: dict) -> str:
    text = str(args)
    return text if len(text) <= 110 else text[:110] + "…"


if __name__ == "__main__":
    try:
        app()
    except SystemExit:
        sys.exit(0)
