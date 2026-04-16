"""
Conversation session — persists exchanges to ~/.saltpepper/sessions/.
"""
import json
import uuid
import time
from datetime import datetime
from pathlib import Path

SESSIONS_DIR = Path.home() / ".saltpepper" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


class Session:
    def __init__(self):
        self.session_id = str(uuid.uuid4())[:8]
        self.created_at = datetime.now().isoformat()
        self.exchanges: list[dict] = []
        self._path = SESSIONS_DIR / f"{self.session_id}.json"

    # ── Mutation ──────────────────────────────────────────────────────────────

    def add_exchange(self, user: str, assistant: str, tier: str):
        self.exchanges.append({
            "user":      user,
            "assistant": assistant,
            "tier":      tier,
            "ts":        datetime.now().isoformat(),
        })

    def clear(self):
        self.exchanges.clear()

    # ── Query ─────────────────────────────────────────────────────────────────

    def get_recent_summary(self, max_turns: int = 3) -> str:
        """Plain-text summary of last N turns for Gemma context."""
        recent = self.exchanges[-max_turns:]
        if not recent:
            return ""
        lines = []
        for ex in recent:
            resp = ex["assistant"][:200].replace("\n", " ")
            lines.append(f"User: {ex['user'][:100]}")
            lines.append(f"Assistant: {resp}…")
        return "\n".join(lines)

    def get_recent_history(self, max_turns: int = 5) -> list:
        """Last N exchanges as list of dicts (for Claude prompt formatting)."""
        return list(self.exchanges[-max_turns:])

    def get_messages_for_litert(self, max_turns: int = 10) -> list:
        """Last N exchanges formatted as role/content message list for LiteRT."""
        messages = []
        for ex in self.exchanges[-max_turns:]:
            messages.append({"role": "user",      "content": ex["user"]})
            messages.append({"role": "assistant",  "content": ex["assistant"]})
        return messages

    def get_recent_prompt(self, max_turns: int = 10) -> str:
        """Last N exchanges as 'User: ... / Assistant: ...' narrative text for Gemma."""
        parts = []
        for ex in self.exchanges[-max_turns:]:
            parts.append(f"User: {ex['user']}")
            parts.append(f"Assistant: {ex['assistant']}")
        return "\n".join(parts)

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self):
        if not self.exchanges:
            return
        data = {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "exchanges":  self.exchanges,
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.rename(self._path)

    @staticmethod
    def prune_old(days: int = 30):
        """Delete sessions older than N days."""
        cutoff = time.time() - days * 86400
        for f in SESSIONS_DIR.glob("*.json"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except OSError:
                pass
