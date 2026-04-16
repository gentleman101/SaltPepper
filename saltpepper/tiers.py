"""Single source of truth for tier metadata."""

TIERS = ("LOCAL", "FAST", "MED", "HIGH")

# ── Display ──────────────────────────────────────────────────────────────────

ICON  = {"LOCAL": "⚡", "FAST": "🚀", "MED": "⚖️ ", "HIGH": "🧠"}
COLOR = {"LOCAL": "green", "FAST": "cyan", "MED": "yellow", "HIGH": "red"}
NAME  = {"LOCAL": "Gemma", "FAST": "Haiku", "MED": "Sonnet", "HIGH": "Opus"}

# ── Model IDs (Claude CLI --model flag) ──────────────────────────────────────

MODEL_ID = {
    "FAST": "claude-haiku-4-5-20251001",
    "MED":  "claude-sonnet-4-6",
    "HIGH": "claude-opus-4-6",
}

# ── Pricing key (for savings tracker) ────────────────────────────────────────

MODEL = {"LOCAL": "gemma", "FAST": "haiku", "MED": "sonnet", "HIGH": "opus"}

# ── Pricing per million tokens (USD) ─────────────────────────────────────────

PRICING = {
    "gemma":  {"input": 0.0,  "output": 0.0},
    "haiku":  {"input": 1.0,  "output": 5.0},
    "sonnet": {"input": 3.0,  "output": 15.0},
    "opus":   {"input": 5.0,  "output": 25.0},
}

# ── Classification thresholds ────────────────────────────────────────────────

CONFIDENCE_FLOOR = {"LOCAL": 0.72, "FAST": 0.65, "MED": 0.60, "HIGH": 0.0}
FALLBACK = {"LOCAL": "FAST", "FAST": "MED", "MED": "HIGH", "HIGH": "MED"}
