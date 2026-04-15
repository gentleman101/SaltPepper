"""
Tests for the vector → Gemma → bias classification pipeline.
Gemma and the embedder are mocked — no model files required to run tests.

Patch paths use saltpepper.router.classifier.* because classifier.py
does `from ... import classify_by_vector, learn, is_learning` — patching
the source module would not affect already-bound names.
"""
import pytest
from unittest.mock import patch

from saltpepper.router.classifier import classify_request

_VEC      = "saltpepper.router.classifier.classify_by_vector"
_LEARN    = "saltpepper.router.classifier.learn"
_LEARNING = "saltpepper.router.classifier.is_learning"
_GEMMA    = "saltpepper.models.gemma.classify"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _gemma(tier: str, confidence: float) -> dict:
    return {"tier": tier, "confidence": confidence, "domains": [], "reasoning": "mock"}


def _vec(tier: str, confidence: float, sim: float = 0.95) -> dict:
    return {"tier": tier, "confidence": confidence, "top_match": "mock", "max_sim": sim}


# ── Stage 1: vector hit → no Gemma ────────────────────────────────────────────

class TestVectorHit:
    def test_vector_hit_skips_gemma(self):
        called = []
        with patch(_VEC, return_value=_vec("LOW", 1.0)), \
             patch(_GEMMA, side_effect=lambda *a, **k: called.append(True) or _gemma("LOW", 0.9)):
            r = classify_request("hi")
        assert r["tier"] == "LOW"
        assert len(called) == 0, "Gemma must not be called on vector hit"

    def test_vector_hit_med(self):
        with patch(_VEC, return_value=_vec("MED", 0.88)):
            r = classify_request("write a sort function")
        assert r["tier"] == "MED"

    def test_vector_hit_high(self):
        with patch(_VEC, return_value=_vec("HIGH", 0.95)):
            r = classify_request("architect a microservices system")
        assert r["tier"] == "HIGH"


# ── Stage 2: vector miss → Gemma fallback ─────────────────────────────────────

class TestGemmaFallback:
    def test_gemma_called_on_vector_miss(self):
        called = []
        with patch(_VEC, return_value=None), \
             patch(_LEARN), \
             patch(_GEMMA, side_effect=lambda *a, **k: called.append(True) or _gemma("MED", 0.85)):
            r = classify_request("some novel question")
        assert len(called) == 1, "Gemma must be called on vector miss"
        assert r["tier"] == "MED"

    def test_gemma_result_is_used(self):
        with patch(_VEC, return_value=None), \
             patch(_LEARN), \
             patch(_GEMMA, return_value=_gemma("HIGH", 0.91)):
            r = classify_request("a complex novel query")
        assert r["tier"] == "HIGH"

    def test_learn_called_when_bank_learning(self):
        learned = []
        with patch(_VEC, return_value=None), \
             patch(_LEARNING, return_value=True), \
             patch(_LEARN, side_effect=lambda msg, tier: learned.append((msg, tier))), \
             patch(_GEMMA, return_value=_gemma("MED", 0.80)):
            classify_request("novel coding question")
        assert len(learned) == 1
        assert learned[0][1] == "MED"

    def test_learn_not_called_when_bank_complete(self):
        learned = []
        with patch(_VEC, return_value=None), \
             patch(_LEARNING, return_value=False), \
             patch(_LEARN, side_effect=lambda msg, tier: learned.append(True)), \
             patch(_GEMMA, return_value=_gemma("MED", 0.80)):
            classify_request("novel coding question")
        assert len(learned) == 0


# ── Stage 3: safety bias ───────────────────────────────────────────────────────

class TestSafetyBias:
    def _run(self, tier, confidence):
        with patch(_VEC, return_value=None), \
             patch(_LEARN), \
             patch(_GEMMA, return_value=_gemma(tier, confidence)):
            return classify_request("any message")

    def test_low_below_threshold_upgrades_to_med(self):
        assert self._run("LOW", 0.69)["tier"] == "MED"

    def test_low_at_threshold_stays_low(self):
        assert self._run("LOW", 0.70)["tier"] == "LOW"

    def test_low_above_threshold_stays_low(self):
        assert self._run("LOW", 0.95)["tier"] == "LOW"

    def test_med_below_threshold_upgrades_to_high(self):
        assert self._run("MED", 0.59)["tier"] == "HIGH"

    def test_med_at_threshold_stays_med(self):
        assert self._run("MED", 0.60)["tier"] == "MED"

    def test_high_never_upgraded(self):
        assert self._run("HIGH", 0.10)["tier"] == "HIGH"


# ── Debug dict ────────────────────────────────────────────────────────────────

class TestDebugDict:
    def test_vector_hit_populates_debug(self):
        dbg = {}
        with patch(_VEC, return_value=_vec("LOW", 1.0, sim=0.97)):
            classify_request("hi", _debug=dbg)
        assert dbg["vector_tier"] == "LOW"
        assert dbg["vector_max_sim"] == pytest.approx(0.97)
        assert dbg["gemma_called"] is False
        assert dbg["final_tier"] == "LOW"

    def test_gemma_fallback_populates_debug(self):
        dbg = {}
        with patch(_VEC, return_value=None), \
             patch(_LEARN), \
             patch(_GEMMA, return_value=_gemma("MED", 0.82)):
            classify_request("novel query", _debug=dbg)
        assert dbg["vector_tier"] is None
        assert dbg["gemma_called"] is True
        assert dbg["gemma_tier"] == "MED"
        assert dbg["final_tier"] == "MED"

    def test_bias_rule_recorded_in_debug(self):
        dbg = {}
        with patch(_VEC, return_value=None), \
             patch(_LEARN), \
             patch(_GEMMA, return_value=_gemma("LOW", 0.50)):
            classify_request("something vague", _debug=dbg)
        assert len(dbg["bias_rules_fired"]) == 1
        assert "LOW" in dbg["bias_rules_fired"][0]
        assert dbg["final_tier"] == "MED"
