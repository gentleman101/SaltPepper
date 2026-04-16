# 🌶️ SaltPepper

> An intelligent router that sits between you and Claude — sending simple questions to a free local model, and only spending API tokens when the task actually demands it.

---

## What Is It

Every time you talk to Claude Code, every message — whether it's "what is a binary tree?" or "architect a distributed auth system" — gets sent to the same expensive Opus model. SaltPepper fixes that.

It intercepts your message, runs it through **Gemma 4 E2B** (a 2.3B parameter model that runs completely free on your machine via LiteRT), and decides which tier the request belongs to — using its own understanding of what each model can and cannot do, not just keyword matching.

| Tier | Model | Cost | Used for |
|------|-------|------|----------|
| ⚡ LOCAL | Gemma 4 E2B (on-device) | Free | Greetings, definitions, simple Q&A |
| 🚀 FAST | Claude Haiku 4.5 | $1/MTok | Quick code, syntax, structured tasks |
| ⚖️ MED | Claude Sonnet 4.6 | $3/MTok | Code generation, debugging, analysis |
| 🧠 HIGH | Claude Opus 4.6 | $5/MTok | Architecture, research, complex reasoning |

The result: most sessions save 40–70% of what they'd cost if everything went to Opus. SaltPepper shows you the savings live, per message, in the terminal.

---

## How It Works

```
You type a message
        │
        ▼
┌──────────────────────────────────────────────┐
│  Gemma reads PEPPER.md (routing constitution) │
│  + saltshaker.md (your personal profile)      │
│  → classifies to minimum viable tier          │
└──────────────┬───────────────────────────────┘
               │
   ┌───────────┼────────────┬────────────┐
LOCAL        FAST          MED          HIGH
   │           │             │             │
 Gemma       Haiku        Sonnet         Opus
 (local)     (API)         (API)          (API)
   │           │             │             │
   └───────────┴─────────────┴─────────────┘
                      │
             Token savings recorded
             saltshaker.md updated at session end
```

**Capability-aware routing:** Gemma doesn't match your message against a bank of examples. It reads `PEPPER.md` — a plain-English document defining exactly what each model handles, with hard capability ceilings — and makes a judgment call about the minimum tier needed.

**Safety bias:** when Gemma isn't confident enough, it always escalates — never downgrades. Quality is never sacrificed for savings.

**Streaming:** all responses — whether from local Gemma or Claude — stream token-by-token with live Markdown rendering via Rich.

---

## Personalisation

SaltPepper gets smarter about *you* the more you use it.

At the end of every session, Gemma reads your conversation log and rewrites `saltshaker.md` — a personal profile stored locally on your machine, never pushed to any server. The profile captures:

- Your primary domains (frontend, backend, DevOps, data science...)
- How complex your questions tend to be per domain
- Routing patterns it's learned (e.g. "your React questions are usually FAST-tier, not MED")
- Signals for what you don't need escalation for

This profile is injected into every classification call alongside `PEPPER.md`. By session 5–10, the router knows your workflow and routes with noticeably fewer over-escalations.

```
~/.saltpepper/kitchen/saltshaker.md   ← Gemma writes this, you own it, never leaves your machine
```

The profile is intentionally human-readable markdown. You can open it, read it, edit it, or delete it to start fresh.

---

## The Guiding Files

```
saltpepper/kitchen/
  PEPPER.md         ← Gemma's routing constitution (in repo, version-controlled)
  spicerack.yaml    ← Capability reference: strengths, hard limits, context windows per tier

~/.saltpepper/kitchen/
  saltshaker.md     ← Your personal profile (local only, Gemma writes this)
```

`PEPPER.md` is the single document Gemma reads before every classification. It defines what each tier handles, confidence thresholds, and worked examples — all in plain English. When a model is upgraded or a new tier is added, update `PEPPER.md`. No code changes needed.

`spicerack.yaml` is the capability reference document — model strengths, hard limits, context windows, and costs. It's human-readable documentation for understanding why the tiers are defined the way they are.

---

## Inspiration

SaltPepper's personalisation architecture is inspired by two ideas:

**[second-brain](https://github.com/NicholasSpisak/second-brain)** by Nicholas Spisak — an LLM-powered personal knowledge system built on Andrej Karpathy's "LLM Wiki" pattern. The key insight borrowed here: LLMs reasoning over human-readable markdown artifacts are more maintainable and more capable than opaque vector databases. Explicit knowledge over implicit similarity.

**Andrej Karpathy's LLM OS concept** — the idea that an LLM should maintain a living, compounding knowledge artifact rather than re-deriving the same conclusions from scratch every time. `saltshaker.md` is SaltPepper's version of that: Gemma's understanding of you compounds with every session instead of resetting.

---

## Quick Start

```bash
git clone https://github.com/gentleman101/SaltPepper.git
cd SaltPepper
python3 makeitsalty.py
```

`makeitsalty.py` handles everything in order:

1. Python version check (3.10+ required)
2. Install Python dependencies
3. Download Gemma 4 E2B model (~1.5 GB, one time, via HuggingFace)
4. Claude Code CLI check and auth
5. Launch `sp`

After setup, just run `sp` from anywhere.

---

## Prerequisites

| Requirement | Check | Install |
|-------------|-------|---------|
| Python 3.10+ | `python3 --version` | `brew install python@3.12` |
| Claude Code CLI | `claude --version` | `npm install -g @anthropic-ai/claude-code` |
| Claude account | `claude auth status` | `claude auth login` |

Gemma 4 E2B downloads automatically on first run. No GPU required — runs on CPU via LiteRT.

---

## Usage

```bash
sp          # launch SaltPepper
```

### What a session looks like

```
You: hey what's up
↳ ⚡ routing to Gemma…

Hey! What can I help you with today?

⚡ LOCAL → Gemma · saved 380 tok
──── Session: 1 msgs │ API: 0 tok │ Saved: 380 (100%) 🌶️ ────

You: fix this debounce function
↳ 🚀 routing to Haiku…

Here's the corrected version…

🚀 FAST → Haiku · saved 890 tok
──── Session: 2 msgs │ API: 210 tok │ Saved: 1,270 (86%) 🌶️ ────

You: architect a microservices auth system for 10M users
↳ 🧠 routing to Opus…

Let me think through this carefully…

🧠 HIGH → Opus · —
──── Session: 3 msgs │ API: 2,840 tok │ Saved: 1,270 (31%) 🌶️ ────
```

### Commands

| Command | What it does |
|---------|-------------|
| `/local` `/fast` `/med` `/high` | Force the next request to a specific tier |
| `/auto` | Return to automatic routing |
| `/insights` | Gemma's analysis of your usage patterns and profile |
| `/stats` | Full breakdown — messages per tier, tokens, cost saved |
| `/status` | Current routing mode and token counts |
| `/history` | Last 10 messages with tier labels |
| `/clear` | Wipe the session and reset counters |
| `/model` | Show or override the model for any tier this session |
| `/account` | Login or switch Claude account |
| `/help` | Show all commands |
| `/quit` | Exit — profile updates automatically |

### Error paste detection

Paste a multi-line error traceback directly into the prompt. SaltPepper detects it automatically and routes it to Gemma for a spicy-voiced diagnosis with numbered fix steps — no need to type "what does this error mean."

---

## Project Structure

```
SaltPepper/
├── makeitsalty.py           ← One-command setup for a new machine
├── saltpepper/
│   ├── tiers.py             ← Single source of truth: model IDs, pricing, confidence floors
│   ├── kitchen/
│   │   ├── PEPPER.md        ← Gemma's routing constitution
│   │   └── spicerack.yaml   ← Tier capability reference (docs only)
│   ├── router/
│   │   ├── grinder.py       ← Capability-aware classifier + profile management
│   │   └── prompts.py       ← Gemma prompt templates
│   ├── models/
│   │   ├── gemma.py         ← LiteRT engine — classify, chat, guide
│   │   └── claude.py        ← claude CLI subprocess with stream-json rendering
│   ├── context/
│   │   └── history.py       ← Session persistence (~/.saltpepper/sessions/)
│   └── tracker/
│       └── savings.py       ← Token savings calculator and status bar
└── pyproject.toml

~/.saltpepper/               ← Runtime files, never committed
├── models/                  ← Gemma 4 E2B model file (~1.5 GB)
├── kitchen/
│   └── saltshaker.md        ← Your personal profile (Gemma writes this)
└── sessions/                ← Conversation history
```

---

## Token Savings — How the Math Works

SaltPepper compares against the baseline: *what would this have cost if every message went to Claude Opus?*

| Tier | Saving vs Opus |
|------|----------------|
| LOCAL (Gemma) | 100% — it's free |
| FAST (Haiku) | ~80% cheaper than Opus |
| MED (Sonnet) | ~40% cheaper than Opus |
| HIGH (Opus) | 0% — this is the baseline |

The percentage in the status bar is: `saved_cost / baseline_cost × 100`

---

## Fallbacks

| Failure | What happens |
|---------|-------------|
| Gemma returns malformed JSON | 3-layer parser strips fences, extracts JSON object, falls back to MED |
| Confidence below threshold | Escalates one tier — never downgrades |
| Claude CLI not installed | Warning shown, LOCAL tier still works |
| Claude auth expired | Friendly message, `/account` to re-auth |
| Session can't be saved | Continues without saving — current conversation unaffected |

---

## Why "SaltPepper"

Salt and pepper sit on every table but you only reach for them when the dish actually needs it. Most conversations don't need Opus. SaltPepper makes sure you only pay for the seasoning the dish requires.
