# SaltPepper — Project Brain

> One source of truth for architecture, state, known issues, and what to do next.
> Keep this file updated as the project evolves.

---

## What It Is

A Python CLI (`sp` / `saltpepper`) that routes AI requests to the cheapest model capable of answering them:

- **LOW** → Gemma 4 E2B (local, free, LiteRT runtime)
- **MED** → Claude Sonnet (paid, subprocess via `claude` CLI)
- **HIGH** → Claude Opus (paid, subprocess via `claude` CLI)

The router is the core product. Everything else is scaffolding.

---

## File Map

```
saltpepper/
├── cli.py                     ← Entry point. REPL loop, commands, downgrade prompt.
├── debug.py                   ← /debug toggle. Gitignored. Shows routing panel.
│
├── router/
│   ├── classifier.py          ← Main pipeline: vector → Gemma → bias → tier
│   ├── vector_classifier.py   ← Similarity search + self-learning user bank
│   ├── embedder.py            ← all-MiniLM-L6-v2 lazy singleton
│   ├── example_bank.json      ← 53 curated examples (21 LOW, 17 MED, 15 HIGH)
│   └── prompts.py             ← CLASSIFY_SYSTEM + CLASSIFY_USER + HISTORY_SUMMARY_PROMPT
│
├── models/
│   ├── gemma.py               ← LiteRT engine + classify() + chat_stream()
│   └── claude.py              ← subprocess wrapper for `claude` CLI (MED/HIGH)
│
├── context/
│   └── history.py             ← Session: stores exchanges, formats for LiteRT/Claude
│
├── tracker/
│   └── savings.py             ← Tracks token counts and cost vs Opus baseline
│
└── config/
    ├── __init__.py            ← CONFIG = deep merge of defaults.yaml + ~/.saltpepper/config.yaml
    └── defaults.yaml          ← All active tunables

tests/
├── test_classifier.py         ← Pipeline tests (vector hit, Gemma fallback, bias, debug dict)
└── test_savings.py            ← SavingsTracker math tests
```

---

## Classification Pipeline

```
User message
     │
     ▼
classify_by_vector(message)
     │
     ├── shared_bank (example_bank.json, 53 entries, embedded at import)
     └── user_bank   (~/.saltpepper/user_bank.json, grows over time)
         │
         ├── sim >= threshold? ──YES──▶ {tier, confidence}  (no Gemma call)
         │
         └── NO
              │
              ▼
         gemma.classify(message)   ← no history, avoids context bias
              │
              └── if is_learning(): learn(message, tier)  [background thread]
     │
     ▼
Safety bias:
  LOW  conf < 0.70 → upgrade to MED
  MED  conf < 0.60 → upgrade to HIGH
     │
     ▼
tier in (MED, HIGH)?
  YES → _prompt_downgrade()  [5s timeout: Y=proceed, d=downgrade, n=cancel]
     │
     ▼
route_and_respond()
```

### Adaptive threshold
| Phase | Threshold | Condition |
|---|---|---|
| Learning | 0.80 | user_bank size < bank_limit |
| Complete | 0.90 | user_bank size >= bank_limit |

---

## Key Constants & Where They Live

| Constant | Value | File | Config-driven? |
|---|---|---|---|
| `_THRESHOLD_LEARNING` | 0.80 | vector_classifier.py:12 | No |
| `_THRESHOLD_COMPLETE` | 0.90 | vector_classifier.py:13 | No |
| `_TOP_K` | 5 | vector_classifier.py:15 | No |
| `_BANK_LIMIT` | 1000 | vector_classifier.py | Yes — `CONFIG["memory"]["bank_limit"]` |
| bias LOW threshold | 0.70 | classifier.py:78 | No — config has it but code doesn't read it |
| bias MED threshold | 0.60 | classifier.py:82 | No — config has it but code doesn't read it |
| `classify_timeout` | 5 | gemma.py:69 | No |
| `chat_timeout` | 120 | gemma.py:133 | No |

> **Improvement opportunity:** wire `routing.low_confidence_threshold`, `routing.med_confidence_threshold`, and `litert.*_timeout` from `defaults.yaml` into the code instead of hardcoding.

---

## Runtime Files (live in ~/.saltpepper/, never committed)

```
~/.saltpepper/
├── models/
│   ├── gemma-4-E2B-it.litertlm   ← ~1.5GB, downloaded once via pull_model()
│   └── cache/                     ← LiteRT cache dir
├── user_bank.json                 ← Self-learned examples (grows to bank_limit)
├── sessions/
│   └── <uuid8>.json               ← One file per session
└── config.yaml                    ← Optional user overrides (deep-merged over defaults)
```

---

## CLI Commands

| Command | What it does |
|---|---|
| `/low` `/med` `/high` | Force next request to that tier |
| `/auto` | Return to auto routing |
| `/stats` | Detailed token/cost breakdown |
| `/status` | Quick routing mode + token count |
| `/history` | Last 10 exchanges (user side) |
| `/clear` | Wipe session + reset tracker |
| `/memory status` | Show user_bank size + learning state |
| `/memory reset` | Delete user_bank.json, restart learning |
| `/memory limit N` | Set bank_limit for this session |
| `/debug` | Toggle routing debug panel |
| `/help` | Show all commands |
| `/quit` `/exit` `/q` | Exit and save session |

---

## Debug Panel Keys (when /debug is ON)

```
VECTOR        tier, confidence, max_sim, top_match  (or "none — fell through to Gemma")
MEMORY        bank: learning | complete
GEMMA         called yes/no, tier, confidence
SAFETY BIAS   fired rules or "none"
FINAL         tier + confidence
```

---

## Test Coverage

| File | What it covers | Status |
|---|---|---|
| `test_classifier.py` | Vector hit skips Gemma, Gemma fallback, learn() calls, safety bias (all 6 cases), debug dict shape | ✓ 16/16 passing |
| `test_savings.py` | SavingsTracker math, cost calc, tier distribution, reset, status bar | ✓ 14/14 passing |

**No test coverage for:**
- `vector_classifier.py` — learn(), reset_user_bank(), threshold adaptation, concurrent writes
- `embedder.py` — model loading, cosine_sim
- `cli.py` — command parsing, downgrade prompt
- `gemma.py` — LiteRT engine, classify() JSON parser layers
- `history.py` — session save/load
- `claude.py` — subprocess wrapper

---

## Known Issues (post-cleanup)

### Minor — low priority

1. **Config thresholds not wired** — `defaults.yaml` defines `routing.low_confidence_threshold: 0.70` and `routing.med_confidence_threshold: 0.60` but `classifier.py` hardcodes the same values. Same for litert timeouts.

2. **`Session.prune_old()`** — method exists in `history.py` but is never called. Either hook into startup or remove.

3. **`session.max_history_for_context`** in `defaults.yaml` defined as 5, but `claude.py` hardcodes `history[-5:]`. Should read from config.

---

## Dependency Stack

```
sentence-transformers>=2.7.0   ← vector embeddings (all-MiniLM-L6-v2, ~80MB, auto-downloaded)
numpy>=1.24.0                  ← cosine similarity math
litert-lm-api>=0.10.1          ← Google LiteRT runtime for Gemma
huggingface_hub>=0.23.0        ← model download (hf_hub_download)
rich>=13.0.0                   ← terminal UI
pyyaml>=6.0                    ← config loading
pytest>=7.0                    ← tests
```

External:
- `claude` CLI (`npm install -g @anthropic-ai/claude-code`) — MED/HIGH routing

---

## Possible Next Steps

- [ ] Wire config thresholds/timeouts into classifier.py and gemma.py
- [ ] Add tests for `vector_classifier.py` (learn, reset, threshold adaptation)
- [ ] Hook `Session.prune_old()` into startup
- [ ] `/export` command to dump conversation as markdown
- [ ] Configurable model per tier (e.g. swap Sonnet for Haiku on MED)
