"""
Main classification logic.
Pipeline: vector similarity → Gemma fallback + self-learning → relaxed safety bias.
"""
from saltpepper.router.vector_classifier import classify_by_vector, learn, is_learning
from saltpepper.models import gemma


def classify_request(
    message: str,
    _debug: dict | None = None,
) -> dict:
    """
    Classify a message and return {"tier", "confidence", "domains"}.

    Stage 1 — Vector similarity:
      Searches shared_bank + user_bank combined.
      Threshold adapts: 0.80 while learning, 0.90 once bank is complete.
      Hit  → return immediately, no Gemma call.
      Miss → Stage 2.

    Stage 2 — Gemma fallback:
      No history passed — avoids context bias.
      Result is saved to user_bank in a background thread if still learning.

    Safety bias (relaxed):
      LOW  with confidence < 0.70 → upgrade to MED
      MED  with confidence < 0.60 → upgrade to HIGH

    _debug: if a dict is passed, intermediate state is written into it for
            the debug panel in cli.py. Pass None (default) for zero overhead.
    """
    # Stage 1: vector similarity
    vec = classify_by_vector(message)

    if _debug is not None:
        _debug.update({
            "vector_tier":       vec["tier"]       if vec else None,
            "vector_confidence": vec["confidence"] if vec else None,
            "vector_top_match":  vec["top_match"]  if vec else None,
            "vector_max_sim":    vec["max_sim"]     if vec else None,
            "learning_active":   is_learning(),
            "bias_rules_fired":  [],
        })

    if vec is not None:
        tier       = vec["tier"]
        confidence = vec["confidence"]
        domains: list = []
        if _debug is not None:
            _debug.update({
                "gemma_called":      False,
                "gemma_skip_reason": f"sim={vec['max_sim']:.2f} >= threshold",
                "gemma_tier":        None,
                "gemma_confidence":  None,
            })
    else:
        # Stage 2: Gemma fallback (no history — avoids context bias)
        result     = gemma.classify(message)
        tier       = result["tier"]
        confidence = result["confidence"]
        domains    = result.get("domains", [])

        if _debug is not None:
            _debug.update({
                "gemma_called":      True,
                "gemma_skip_reason": None,
                "gemma_tier":        tier,
                "gemma_confidence":  confidence,
            })

        # Self-learning: persist to user bank in background if still learning
        if is_learning():
            learn(message, tier)

    # Safety bias — relaxed thresholds
    if tier == "LOW" and confidence < 0.70:
        tier = "MED"
        if _debug is not None:
            _debug["bias_rules_fired"].append(f"LOW conf {confidence:.2f} < 0.70 → MED")
    elif tier == "MED" and confidence < 0.60:
        tier = "HIGH"
        if _debug is not None:
            _debug["bias_rules_fired"].append(f"MED conf {confidence:.2f} < 0.60 → HIGH")

    if _debug is not None:
        _debug["final_tier"]       = tier
        _debug["final_confidence"] = confidence

    return {"tier": tier, "confidence": confidence, "domains": domains}
