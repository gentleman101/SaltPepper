# 🌶️ SaltPepper

> An intelligent router that sits between you and Claude — sending simple questions to a free local model, and only spending API tokens when the task actually demands it.

---

## What Is It

Every time you talk to Claude Code, every message — whether it's "what is a binary tree?" or "architect a distributed auth system" — gets sent to the same expensive Opus model. SaltPepper fixes that.

It intercepts your message, runs it through **Gemma 4 E2B** (a 2.3B parameter model that runs completely free on your machine via LiteRT), and decides which tier the request belongs to — using its own understanding of what each model can and cannot do, not just text similarity.

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
┌─────────────────────────────────────────────┐
│  Gemma reads PEPPER.md (routing constitution)│
│  + saltshaker.md (your personal profile)     │
│  → classifies to minimum viable tier         │
└──────────────┬──────────────────────────────┘
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

**Capability-aware routing:** Gemma doesn't match your message against a bank of examples. It reads `PEPPER.md` — a plain-English document defining exactly what each model handles, with hard capability ceilings — and makes a judgment call. The routing gets more accurate over time as `saltshaker.md` builds up a profile of your domains and patterns.

**Safety bias:** when Gemma isn't confident, it always escalates the tier — never downgrades. Quality is never sacrificed for savings.

---

## The Guiding Files

```
saltpepper/kitchen/
  PEPPER.md         ← Gemma's routing constitution (in repo, version-controlled)
  spicerack.yaml    ← Structured capability map for all 4 tiers

~/.saltpepper/kitchen/
  saltshaker.md     ← Your personal profile (local, Gemma writes this, never pushed)
```

`PEPPER.md` is the single guiding document Gemma reads before every classification. It defines what each tier handles, hard ceilings, confidence thresholds, and worked examples. When a model is upgraded or a new Claude tier is added, update `PEPPER.md` — no code changes needed.

`saltshaker.md` starts empty and grows. After every session, Gemma reads your exchanges and updates it: your domains, your typical complexity patterns, what it's learned to pre-route with high confidence. By session 5–10 it knows your workflow.

---

## Inspiration

The user profile architecture is inspired by two ideas:

- **[second-brain](https://github.com/NicholasSpisak/second-brain)** by Nicholas Spisak — an LLM-powered personal knowledge system built on Andrej Karpathy's "LLM Wiki" pattern. The key insight borrowed here: LLMs reasoning over human-readable markdown artifacts (like `PEPPER.md` and `saltshaker.md`) are more maintainable and more capable than opaque vector databases. Explicit connections over implicit similarity.

- **[Andrej Karpathy's LLM OS / LLM Wiki concept](https://karpathy.ai)** — the idea that an LLM should maintain a living, compounding knowledge artifact rather than re-deriving the same conclusions from scratch every time. `saltshaker.md` is SaltPepper's version of that: Gemma's understanding of you compounds with every session.

---

## Quick Start

```bash
git clone https://github.com/gentleman101/SaltPepper.git
cd SaltPepper
python3 makeitsalty.py
```

`makeitsalty.py` handles everything: Python check → install deps → download Gemma model (~1.5 GB, one time) → Claude auth → launch. Once done, just type `sp` from anywhere.

---

## Prerequisites

| Requirement | Check | Install |
|-------------|-------|---------|
| Python 3.10+ | `python3 --version` | `brew install python@3.12` |
| Claude Code CLI | `claude --version` | `npm install -g @anthropic-ai/claude-code` |
| Claude auth | `claude auth status` | `claude auth login` |

Gemma 4 E2B is downloaded automatically on first run via HuggingFace.

---

## Usage

```bash
sp          # launch SaltPepper
```

### What a session looks like

```
You: hey what's up
↳ ⚡ routing to LOCAL (Gemma)…

Hey! What can I help you with today?

⚡ LOCAL → Gemma · saved 380 tok
──── Session: 1 msgs │ API: 0 tok │ Saved: 380 (100%) 🌶️ ────

You: fix this debounce function
↳ 🚀 routing to FAST (Haiku)…

Here's the corrected version…

🚀 FAST → Haiku · saved 890 tok
──── Session: 2 msgs │ API: 210 tok │ Saved: 1,270 (86%) 🌶️ ────

You: architect a microservices auth system for 10M users
↳ 🧠 routing to HIGH (Opus)…

Let me think through this carefully…

🧠 HIGH → Opus · —
──── Session: 3 msgs │ API: 2,840 tok │ Saved: 1,270 (31%) 🌶️ ────
```

### Commands

| Command | What it does |
|---------|-------------|
| `/local` `/fast` `/med` `/high` | Force the next request to a specific tier |
| `/auto` | Return to automatic routing |
| `/insights` | Gemma's analysis of your usage patterns and savings |
| `/stats` | Full breakdown — messages per tier, tokens, cost saved |
| `/status` | Current routing mode and token counts |
| `/history` | Last 10 messages with tier labels |
| `/clear` | Wipe the session and reset counters |
| `/account` | Login or switch Claude account |
| `/help` | Show all commands |
| `/quit` | Exit (profile updates automatically) |

### Error paste detection

Paste a multi-line error traceback directly into the prompt — SaltPepper detects it and routes it to Gemma for spicy-voiced diagnosis with numbered fix steps. No need to type "what does this error mean."

---

## Project Structure

```
SaltPepper/
├── makeitsalty.py           ← One-command setup for a new machine
├── saltpepper/
│   ├── kitchen/
│   │   ├── PEPPER.md        ← Gemma's routing constitution
│   │   └── spicerack.yaml   ← Capability map for all 4 tiers
│   ├── router/
│   │   ├── grinder.py       ← Capability-aware classifier
│   │   └── prompts.py       ← Gemma prompt templates
│   ├── models/
│   │   ├── gemma.py         ← LiteRT engine — classify, chat, guide
│   │   └── claude.py        ← claude CLI subprocess, tier → model mapping
│   ├── context/
│   │   └── history.py       ← Session persistence (~/.saltpepper/sessions/)
│   ├── tracker/
│   │   └── savings.py       ← Token savings calculator and status bar
│   └── config/
│       └── defaults.yaml    ← All defaults
└── pyproject.toml

~/.saltpepper/
├── models/                  ← Gemma 4 E2B model file (~1.5 GB)
├── kitchen/
│   └── saltshaker.md        ← Your profile (Gemma writes, never pushed)
└── sessions/                ← Conversation history
```

---

## Token Savings — How the Math Works

SaltPepper always compares against the baseline: *what would this have cost if every message went to Claude Opus?*

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
| Gemma returns malformed JSON | Parser strips fences, extracts JSON object, falls back to MED |
| Confidence below threshold | Escalates one tier — never downgrades |
| Claude CLI not installed | Warning shown, LOCAL tier still works |
| Claude auth expired | Friendly message, `/account` to re-auth |
| Session can't be saved | Continues without saving — current conversation unaffected |

---

## Why "SaltPepper"

Salt and pepper sit on every table but you only reach for them when the dish actually needs it. Most conversations don't need Opus. SaltPepper makes sure you only pay for the seasoning the dish requires.
