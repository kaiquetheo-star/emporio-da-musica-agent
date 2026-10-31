"""Entry point: ``python main.py`` starts the chat CLI (no install needed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from emporio_agent.cli import app  # noqa: E402

if __name__ == "__main__":
    app()
