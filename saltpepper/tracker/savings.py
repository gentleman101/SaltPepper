"""
Token savings tracker.
Compares actual cost against the Opus-for-everything baseline.
"""
from saltpepper import tiers as _tiers


def estimate_tokens(text: str) -> int:
    """Rough token count estimate: 4 chars ≈ 1 token."""
    return len(text) // 4


def _cost(input_tok: int, output_tok: int, model: str) -> float:
    p = _tiers.PRICING.get(model, _tiers.PRICING["sonnet"])
    return (input_tok * p["input"] + output_tok * p["output"]) / 1_000_000


def _cost_to_opus_tokens(usd: float) -> int:
    """Express a USD saving as equivalent Opus *input* tokens."""
    price_per_tok = _tiers.PRICING["opus"]["input"] / 1_000_000
    return int(usd / price_per_tok) if price_per_tok else 0


class SavingsTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        self.messages     = 0
        self.distribution = {"LOCAL": 0, "FAST": 0, "MED": 0, "HIGH": 0}
        self.actual_tokens  = 0    # paid-API tokens only (Gemma = 0)
        self._actual_cost   = 0.0
        self._baseline_cost = 0.0

    # ── Record ────────────────────────────────────────────────────────────────

    def record(self, tier: str, input_tok: int, output_tok: int) -> int:
        """
        Record one exchange. Returns tokens-saved for this call
        (expressed as Opus-equivalent input tokens).
        """
        self.messages += 1
        self.distribution[tier] = self.distribution.get(tier, 0) + 1

        model = _tiers.MODEL.get(tier, "sonnet")

        actual_call   = _cost(input_tok, output_tok, model)
        baseline_call = _cost(input_tok, output_tok, "opus")

        self._actual_cost   += actual_call
        self._baseline_cost += baseline_call

        if model != "gemma":
            self.actual_tokens += input_tok + output_tok

        saved_usd = baseline_call - actual_call
        return _cost_to_opus_tokens(saved_usd)

    # ── Read ──────────────────────────────────────────────────────────────────

    @property
    def saved_cost(self) -> float:
        return max(0.0, self._baseline_cost - self._actual_cost)

    @property
    def saved_tokens(self) -> int:
        return _cost_to_opus_tokens(self.saved_cost)

    def savings_pct(self) -> int:
        if self._baseline_cost == 0:
            return 0
        return int(self.saved_cost / self._baseline_cost * 100)

    def get_stats(self) -> dict:
        return {
            "messages":       self.messages,
            "distribution":   dict(self.distribution),
            "actual_tokens":  self.actual_tokens,
            "actual_cost":    self._actual_cost,
            "baseline_tokens": _cost_to_opus_tokens(self._baseline_cost),
            "baseline_cost":  self._baseline_cost,
            "saved_tokens":   self.saved_tokens,
            "saved_cost":     self.saved_cost,
        }

    # ── Formatting ────────────────────────────────────────────────────────────

    def format_status_bar(self) -> str:
        pct  = self.savings_pct()
        icon = "🌶️" if pct >= 40 else ("🌶" if pct >= 20 else "")
        saved_str = f"{self.saved_tokens:,} ({pct}%)" if pct > 0 else "0"
        return (
            f"Session: {self.messages} msgs"
            f" │ API: {self.actual_tokens:,} tok"
            f" │ Saved: {saved_str} {icon}"
        ).strip()
