.PHONY: install dev run test test-cov lint clean help

# ── Setup ──────────────────────────────────────────────────────────────────────

install:        ## Install production dependencies
	pip3 install -e .

dev:            ## Install with dev extras (pytest, ruff)
	pip3 install -e ".[dev]"

# ── Run ────────────────────────────────────────────────────────────────────────

run:            ## Start a SaltPepper session
	python3 -m saltpepper

# ── Test ───────────────────────────────────────────────────────────────────────

test:           ## Run all tests
	pytest tests/ -v

test-cov:       ## Run tests with coverage report
	pytest tests/ -v --cov=saltpepper --cov-report=term-missing

test-fast:      ## Run only tests that don't need Ollama/Claude
	pytest tests/test_signals.py tests/test_savings.py tests/test_classifier.py -v

# ── Quality ────────────────────────────────────────────────────────────────────

lint:           ## Run ruff linter
	ruff check saltpepper/ tests/

lint-fix:       ## Run ruff with auto-fix
	ruff check --fix saltpepper/ tests/

# ── Clean ──────────────────────────────────────────────────────────────────────

clean:          ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf dist/ build/ *.egg-info .pytest_cache .ruff_cache

# ── Help ───────────────────────────────────────────────────────────────────────

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
