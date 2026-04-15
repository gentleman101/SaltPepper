"""Single source of truth for tier metadata."""

TIERS = ("LOCAL", "FAST", "MED", "HIGH")

ICON  = {"LOCAL": "⚡", "FAST": "🚀", "MED": "⚖️ ", "HIGH": "🧠"}
COLOR = {"LOCAL": "green", "FAST": "cyan", "MED": "yellow", "HIGH": "red"}
NAME  = {"LOCAL": "Gemma", "FAST": "Haiku", "MED": "Sonnet", "HIGH": "Opus"}
MODEL = {"LOCAL": "gemma", "FAST": "haiku", "MED": "sonnet", "HIGH": "opus"}
