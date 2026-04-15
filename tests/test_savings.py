"""Tests for savings tracker — pure math, no external dependencies."""
import pytest
from saltpepper.tracker.savings import SavingsTracker


class TestLowTier:
    def test_saves_something(self):
        t = SavingsTracker()
        saved = t.record("LOW", 100, 200)
        assert saved > 0

    def test_no_api_tokens_consumed(self):
        t = SavingsTracker()
        t.record("LOW", 100, 200)
        assert t.actual_tokens == 0  # Gemma is local/free

    def test_100_pct_savings(self):
        t = SavingsTracker()
        t.record("LOW", 500, 500)
        assert t.savings_pct() == 100


class TestHighTier:
    def test_no_savings(self):
        t = SavingsTracker()
        saved = t.record("HIGH", 100, 200)
        assert saved == 0

    def test_consumes_api_tokens(self):
        t = SavingsTracker()
        t.record("HIGH", 100, 200)
        assert t.actual_tokens == 300

    def test_zero_pct_savings(self):
        t = SavingsTracker()
        t.record("HIGH", 500, 500)
        assert t.savings_pct() == 0


class TestMedTier:
    def test_saves_some(self):
        t = SavingsTracker()
        saved = t.record("MED", 1000, 500)
        assert saved > 0

    def test_saves_less_than_low(self):
        t1 = SavingsTracker()
        t2 = SavingsTracker()
        low_saved = t1.record("LOW", 1000, 500)
        med_saved = t2.record("MED", 1000, 500)
        assert low_saved > med_saved

    def test_consumes_api_tokens(self):
        t = SavingsTracker()
        t.record("MED", 100, 200)
        assert t.actual_tokens == 300


class TestMixedSession:
    def test_distribution_tracking(self):
        t = SavingsTracker()
        t.record("LOW",  100, 100)
        t.record("MED",  100, 100)
        t.record("HIGH", 100, 100)
        assert t.messages == 3
        assert t.distribution == {"LOW": 1, "MED": 1, "HIGH": 1}

    def test_reset(self):
        t = SavingsTracker()
        t.record("LOW", 1000, 1000)
        t.reset()
        assert t.messages == 0
        assert t.actual_tokens == 0
        assert t.saved_cost == 0.0

    def test_savings_pct_mixed(self):
        t = SavingsTracker()
        t.record("LOW",  500, 500)   # 100% saved
        t.record("HIGH", 500, 500)   # 0% saved
        pct = t.savings_pct()
        assert 0 < pct < 100


class TestStatusBar:
    def test_format_no_sessions(self):
        t = SavingsTracker()
        bar = t.format_status_bar()
        assert "0 msgs" in bar

    def test_format_with_savings(self):
        t = SavingsTracker()
        t.record("LOW", 1000, 1000)
        bar = t.format_status_bar()
        assert "100%" in bar
