"""Conversation history with optional JSONL persistence.

Memory is kept in-process per session (a real deployment would use Redis or
a database — see README "Limitations"). Sessions can be saved to
``conversations/<timestamp>.jsonl`` so demos and interaction examples are
reproducible from real runs.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import CONVERSATIONS_DIR


class ChatSession:
    """OpenAI-style message history plus a replayable event log."""

    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.events: list[dict] = []

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})
        self._log("user", text)

    def add_assistant(
        self, text: str, tool_calls: list[dict] | None = None
    ) -> None:
        self.messages.append({"role": "assistant", "content": text})
        self._log("assistant", text, tool_calls=tool_calls)

    def _log(
        self, role: str, text: str, tool_calls: list[dict] | None = None
    ) -> None:
        self.events.append(
            {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "role": role,
                "text": text,
                **({"tool_calls": tool_calls} if tool_calls else {}),
            }
        )

    def reset(self) -> None:
        self.messages.clear()
        self.events.clear()

    def save(self, directory: Path = CONVERSATIONS_DIR) -> Path:
        """Persist the session as JSONL and return the file path."""
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = directory / f"session-{stamp}.jsonl"
        path.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in self.events),
            encoding="utf-8",
        )
        return path
