# 🌶️ SaltPepper

> An intelligent router that sits between you and Claude — sending simple questions to a free local model, and only spending API tokens when the task actually demands it.

---

## What Is It

Every time you talk to Claude Code, every message — whether it's "what is a binary tree?" or "architect a distributed auth system" — gets sent to the same expensive Opus model. SaltPepper fixes that.

It intercepts your message, runs it through **Gemma 4 E2B** (a small, fast model that runs completely free on your machine via Ollama), and decides in about 200ms which tier the request belongs to:

| Tier | Model | Cost | Used for |
|------|-------|------|----------|
| ⚡ LOW | Gemma 4 E2B (local) | Free | Greetings, definitions, simple Q&A |
| ⚖️ MED | Claude Sonnet | ~80% cheaper than Opus | Code tasks, debugging, explanations |
| 🧠 HIGH | Claude Opus | Full price | Architecture, system design, complex analysis |

The result: most sessions end up saving 40–60% of what they'd cost if everything went to Opus. SaltPepper shows you the savings live, per message, in the terminal.

---

## How It Works

```
You type a message
        │
        ▼
┌───────────────────────────────────┐
│   Pre-signal analysis (instant)   │  ← keyword patterns, word count
│   If obvious → skip Gemma call    │
└──────────────┬────────────────────┘
               │ (if uncertain)
               ▼
┌───────────────────────────────────┐
│   Gemma 4 E2B classifier (~200ms) │  ← runs locally, always free
│   Returns: tier + confidence      │
└──────────────┬────────────────────┘
               │
     ┌─────────┼──────────┐
  LOW│      MED│       HIGH│
     ▼         ▼           ▼
  Gemma     Sonnet       Opus
  (local)   (API)        (API)
     │         │           │
     └─────────┴───────────┘
               │
        Token savings recorded
        Status bar updated
```

**Safety bias:** when Gemma isn't confident, it always upgrades the tier — never downgrades. A misrouted simple question to Opus wastes a few cents. A misrouted architecture question to Gemma wastes your time. SaltPepper is tuned to avoid the latter.

---

## Prerequisites

| Requirement | Check | Install |
|-------------|-------|---------|
| macOS 12+ | `sw_vers` | — |
| Python 3.10+ | `python3 --version` | `brew install python@3.12` |
| Ollama | `ollama --version` | `brew install ollama` |
| Gemma 4 E2B | `ollama list` | auto-pulled on first run |
| Claude Code CLI | `claude --version` | `npm install -g @anthropic-ai/claude-code` |
| Claude auth | `claude auth status` | `claude auth login` |

---

## Installation

```bash
# Clone
git clone https://github.com/your-username/SaltPepper.git
cd SaltPepper

# Install Python dependencies
pip3 install rich pyyaml requests

# (Optional) Add a shell alias
echo "alias sp='python3 $(pwd)/saltpepper.py'" >> ~/.zshrc
source ~/.zshrc
```

On first launch, SaltPepper will:
1. Check if Ollama is running — start it automatically if not
2. Pull `gemma4:e2b` (~1.5 GB, one time only)
3. Drop you into the interactive session

---

## Usage

### Start a session

```bash
python3 saltpepper.py
# or, with the alias:
sp
```

### What a session looks like

```
You: hey what's up
↳ ⚡ routing to Gemma…

Hey! What can I help you with today?

⚡ LOW → Gemma · saved 380 tok
──── Session: 1 msgs │ API: 0 tok │ Saved: 380 (100%) 🌶️ ────

You: write a react login form with JWT auth
↳ ⚖️  routing to Sonnet…

Here's a login component...

⚖️  MED → Sonnet · saved 1,240 tok
──── Session: 2 msgs │ API: 620 tok │ Saved: 1,620 (72%) 🌶️ ────

You: architect a microservices auth system for 10M users
↳ 🧠 routing to Opus…

Let me think through this carefully...

🧠 HIGH → Opus · — 
──── Session: 3 msgs │ API: 2,840 tok │ Saved: 1,620 (36%) 🌶️ ────
```

### Commands

| Command | What it does |
|---------|-------------|
| `/low` `/med` `/high` | Force the next request to a specific tier (one-shot) |
| `/auto` | Return to automatic classification |
| `/stats` | Full breakdown — messages per tier, tokens, cost saved |
| `/status` | Current routing mode and token counts |
| `/history` | Last 10 messages with tier labels |
| `/clear` | Wipe the session and reset counters |
| `/help` | Show all commands |
| `/quit` | Exit and save session |

### `/stats` output

```
─────────────── SaltPepper Stats 🌶️ ───────────────
Messages: 24
  ⚡ LOW  (Gemma  ):   8  (33%)
  ⚖️  MED  (Sonnet ):  12  (50%)
  🧠 HIGH (Opus   ):   4  (17%)

Tokens:
  Baseline (all Opus):      21,000
  Actual API used:           8,400
  Saved:                    12,600  (60%)

Cost:
  Baseline:  $1.5800
  Actual:    $0.4100
  Saved:     $1.1700
────────────────────────────────────────────────────
```

### Force a tier

If you know what you need, skip classification entirely:

```
You: /high
↳ next request forced to HIGH

You: review the security of this authentication flow...
↳ 🧠 routing to Opus (forced)…
```

### Per-project config

Create `~/.saltpepper/config.yaml` to override any default:

```yaml
ollama:
  model: "gemma3:4b"          # use a different local model
  classify_timeout: 5         # give Gemma more time on slow hardware

routing:
  low_confidence_threshold: 0.95   # be more aggressive about upgrading LOW
```

---

## Token Savings — How the Math Works

SaltPepper always compares against the same baseline: *what would this have cost if every message went to Claude Opus with no optimization?*

**LOW tier (Gemma):**
- Baseline: estimated input + output tokens × Opus price
- Actual: $0.00 (local)
- Saved: 100% of the baseline cost, expressed as equivalent Opus tokens

**MED tier (Sonnet vs Opus):**
- Sonnet is 80% cheaper than Opus per token
- Saved tokens = cost difference expressed in Opus token equivalents

**HIGH tier (Opus):**
- No savings — this is the baseline model
- Still tracked so the percentage stays accurate

**The percentage** shown in the status bar is:
```
saved / (saved + actual) × 100
```

---

## Fallbacks

SaltPepper is designed around one rule: **it must never block you from working.** Every failure has a defined recovery path.

### Ollama is not running
SaltPepper tries to start it automatically via `ollama serve`. If that fails (Ollama not installed, port conflict), it prints install instructions and exits cleanly. It does not attempt to proceed without a classifier.

### Gemma model not pulled
Detected at startup. Pulls automatically on first run with a progress bar. If the pull fails, it shows the manual command (`ollama pull gemma4:e2b`) and exits.

### Gemma hangs / responds slowly
Classification has a 3-second timeout. On timeout, the request is routed to Sonnet (MED) as a safe default — not Opus (no wasted spend), not Gemma (known to be slow right now).

### Gemma returns malformed JSON
The response parser strips markdown fences, finds the JSON object within any surrounding text, and falls back to `{"tier": "MED", "confidence": 0.5}` if parsing still fails. You never see this error.

### Claude CLI not installed
Detected at startup — a warning is shown but SaltPepper continues. LOW-tier (Gemma) requests still work. MED/HIGH requests show a friendly error with the install command.

### Claude auth expired or missing
Detected when `claude -p` exits non-zero with auth-related stderr. SaltPepper prints "Claude auth required — run: claude auth login" and returns to the prompt without crashing.

### Disk full / session can't be saved
Session saving uses atomic writes (write to `.tmp`, then rename). If the write fails, SaltPepper continues without saving — your current conversation is unaffected.

### Everything breaks at once
If routing fails at any level, SaltPepper catches the exception, prints the error, and returns to the prompt. You can retry, switch tiers manually with `/med` or `/high`, or just run `claude` directly in another terminal.

---

## Configuration Reference

All defaults live in `config/defaults.yaml`. Override in `~/.saltpepper/config.yaml`.

```yaml
ollama:
  base_url: "http://localhost:11434"
  model: "gemma4:e2b"
  classify_timeout: 3      # seconds before defaulting to MED
  chat_timeout: 120        # max seconds for a Gemma response

routing:
  low_confidence_threshold: 0.90   # below this, LOW → MED
  med_confidence_threshold: 0.85   # below this, MED → HIGH
  default_tier: "MED"              # fallback when classification fails

session:
  save: true
  prune_days: 30           # auto-delete sessions older than 30 days

pricing:                   # per million tokens (USD) — used for savings calc
  opus:
    input: 15.0
    output: 75.0
  sonnet:
    input: 3.0
    output: 15.0
```

---

## Project Structure

```
SaltPepper/
├── saltpepper.py            # Entry point — REPL loop, UI, startup checks
├── router/
│   ├── classifier.py        # Combines signals + Gemma, applies safety bias
│   ├── prompts.py           # Gemma prompt templates
│   └── signals.py           # Keyword pre-classification (no Gemma call)
├── models/
│   ├── gemma.py             # Ollama API — classify() + chat_stream()
│   └── claude.py            # claude -p subprocess with live streaming
├── context/
│   └── history.py           # Conversation persistence (~/.saltpepper/sessions/)
├── tracker/
│   └── savings.py           # Token savings calculator and status bar
├── config/
│   ├── __init__.py          # Config loader with user override merging
│   └── defaults.yaml        # All defaults
└── requirements.txt         # rich, pyyaml, requests
```

Sessions are stored at `~/.saltpepper/sessions/<id>.json` and pruned automatically after 30 days.

---

## Roadmap

- **Phase 2 — Prompt Intelligence:** opt-in prompt compression before paid API calls, with preservation rules (never alter code blocks, error messages, or constraints) and self-verification
- **Phase 3 — Project Intelligence:** `saltpepper init` generates a tagged CLAUDE.md via Haiku; selective context loading injects only the relevant sections per request domain

---

## Why "SaltPepper"

Salt and pepper sit on every table but you only reach for them when the dish actually needs it. Most conversations don't need Opus. SaltPepper makes sure you only pay for the seasoning the dish requires.
