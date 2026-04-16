# SaltPepper — Project Brain

> Single source of truth for architecture, state, known issues, and next steps.
> Update this file after every significant change.

---

## What It Is

A Python CLI (`sp`) that routes AI requests to the cheapest model capable of answering them without quality loss:

| Tier | Model | Cost | Use |
|---|---|---|---|
| LOCAL | Gemma 4 E2B (LiteRT, on-device) | Free | Greetings, simple Q&A, follow-ups |
| FAST | Claude Haiku 4.5 | $1/$5 per MTok | Quick code snippets, syntax, boilerplate |
| MED | Claude Sonnet 4.6 | $3/$15 per MTok | Coding, debugging, explanations |
| HIGH | Claude Opus 4.6 | $5/$25 per MTok | Architecture, security, deep reasoning |

---

## File Map

```
saltpepper/
├── cli.py                  ← REPL loop, commands, downgrade prompt, error paste detection
│                              Unified Live+Markdown rendering for all tiers via _feed() + Rich Live
├── tiers.py                ← Single source of truth for ALL tier metadata:
│                              ICON, COLOR, NAME, MODEL_ID, MODEL, PRICING,
│                              CONFIDENCE_FLOOR, FALLBACK
├── debug.py                ← /debug toggle + Rich panel. Gitignored.
├── __main__.py             ← python -m saltpepper entry
│
├── router/
│   ├── grinder.py          ← Core classifier. PEPPER.md (lru_cache) + saltshaker (mtime cache)
│   │                          → Gemma → _check_escalation() via tiers.py floors.
│   │                          Also: update_saltshaker() (end-of-session), get_insights() (/insights)
│   └── prompts.py          ← Two active prompts only: SETUP_GUIDE_PROMPT, ERROR_DIAGNOSE_PROMPT
│
├── models/
│   ├── gemma.py            ← LiteRT engine singleton.
│   │                          classify_with_context(full_prompt) → 3-layer JSON parser
│   │                          guide(situation) → one-shot blocking call
│   │                          chat_stream(prompt_or_messages) → token streaming for LOCAL
│   └── claude.py           ← subprocess wrapper for `claude` CLI (FAST/MED/HIGH)
│                              stream-json + --include-partial-messages + --verbose
│                              on_delta callback → caller controls display (Rich Live)
│
├── kitchen/
│   ├── PEPPER.md           ← Gemma's routing constitution. 4 tier definitions with confidence
│   │                          floors inline, 8 worked examples. ~230 tokens. Injected every classify.
│   └── spicerack.yaml      ← Documentation only. Model capabilities, strengths, hard limits.
│                              NOT loaded at runtime (thresholds live in tiers.py now).
│
├── context/
│   └── history.py          ← Session class: stores exchanges, get_recent_prompt() for LOCAL,
│                              get_recent_history() for Claude, saves to ~/.saltpepper/sessions/
│
└── tracker/
    └── savings.py          ← SavingsTracker: actual vs Opus-baseline cost. Reads PRICING from tiers.py.

tests/
└── test_savings.py         ← 14 tests for SavingsTracker math. All passing.

makeitsalty.py              ← First-run setup: model download, Claude auth
```

---

## Classification Pipeline

```
User message
     │
     ▼
grinder.classify_request(message)
     │
     ├── _load_pepper()          → lru_cache — loaded once per process
     ├── _load_saltshaker()      → mtime-checked — reloads only when file changes
     └── Build full prompt: [PEPPER.md] + ---USER PROFILE--- + [saltshaker] + message
     │
     ▼
gemma.classify_with_context(full_prompt)
     │  3-layer JSON parser: fence strip → brace extract → json.loads + validate
     └── returns {"tier", "confidence", "reasoning"}
     │
     ▼
_check_escalation(tier, confidence)     ← uses tiers.CONFIDENCE_FLOOR + tiers.FALLBACK
  LOCAL conf < 0.72 → FAST
  FAST  conf < 0.65 → MED
  MED   conf < 0.60 → HIGH
  HIGH  → no ceiling
     │
     ▼
tier in (FAST, MED, HIGH)?
  YES → _prompt_downgrade() [5s timeout: Y=proceed, d=downgrade, n=cancel]
     │
     ▼
route_and_respond()  ← unified Live+Markdown rendering for all tiers
  LOCAL        → chat_stream(prompt) via get_recent_prompt()
  FAST/MED/HIGH → call_claude(on_delta=_feed) via stream-json subprocess
```

---

## End-of-Session Profile Update

On `/quit`, `grinder.update_saltshaker()` runs:
1. Takes last 20 exchanges as `[TIER] message` lines
2. Passes existing `saltshaker.md` + session log to `gemma.guide()`
3. Gemma rewrites the profile (domains, complexity patterns, routing signals)
4. Written to `~/.saltpepper/kitchen/saltshaker.md`
5. Context cache invalidated — next session picks it up

---

## Runtime Files (~/.saltpepper/, never committed)

```
~/.saltpepper/
├── models/
│   ├── gemma-4-E2B-it.litertlm   ← ~1.5GB, downloaded once
│   └── cache/                     ← LiteRT cache
├── kitchen/
│   └── saltshaker.md              ← Personal profile, updated each session
├── sessions/
│   └── <uuid8>.json               ← One file per session
└── config.yaml                    ← Optional user overrides (not implemented yet)
```

---

## Confidence Scoring — Important Caveat

The confidence number is **self-reported by Gemma** — not a probability, not logprobs, not calibrated. Gemma writes `0.88` because PEPPER.md told it to output a confidence score. There is no mathematical grounding.

The thresholds in `tiers.CONFIDENCE_FLOOR` are the real safety net. Confidence is directionally useful but not reliable at fine granularity (0.71 vs 0.73 is noise).

---

## CLI Commands

| Command | What it does |
|---|---|
| `/local` `/fast` `/med` `/high` | Force next request to that tier |
| `/auto` | Return to auto routing |
| `/stats` | Token/cost breakdown with tier distribution |
| `/status` | Quick routing mode + token count |
| `/history` | Last 10 exchanges |
| `/clear` | Wipe session + reset tracker |
| `/insights` | Gemma analyses your session stats + profile |
| `/model` | Show / override model per tier |
| `/account` | Login or switch Claude account |
| `/debug` | Toggle routing debug panel |
| `/help` | Show all commands |
| `/quit` `/exit` `/q` | Save session, update profile, exit |

---

## Test Coverage

| File | Tests | Status |
|---|---|---|
| `test_savings.py` | SavingsTracker math, cost calc, distribution, reset, status bar | ✓ 14/14 |

**No test coverage for:**
- `grinder.py` — classify_request, update_saltshaker, confidence escalation
- `gemma.py` — LiteRT engine, JSON parser layers, guide()
- `cli.py` — command parsing, downgrade prompt, error paste detection

---

## Pending Work

### 1. Better UI Rendering

**Current state:** Responses from all tiers stream into a Rich `Live(Markdown(...))` block, which renders incrementally as tokens arrive. This is working but basic.

**What's missing:**
- Code blocks inside Markdown responses have no syntax highlighting during streaming — Rich renders them once streaming stops
- No visual separation between turns (just a thin badge line)
- No way to scroll back through past responses in-session

**Guidance:** The streaming-then-render approach is the right architecture. The next step is post-stream enhancement: after the Live block closes, detect if the response contains code blocks and re-render with `rich.syntax.Syntax` for proper highlighting. For turn separation, a styled rule between exchanges (different from the status bar rule) would help readability.

---

### 2. Gemma as an Agentic Layer — Carrying Claude's Weight

**Current state:** Gemma only does two things — classify messages and update the user profile. Every real response goes to Claude (FAST/MED/HIGH), which means even medium-complexity tasks that Gemma could partially handle still burn Claude tokens.

**The opportunity:** Gemma can act as a pre-processor and post-processor that reduces what Claude needs to do:
- **Pre-process:** Gemma reformulates the user's message into a sharper, more precise prompt before it reaches Claude — eliminating ambiguity that forces Claude to ask clarifying questions (a full token-expensive round trip)
- **Post-process:** For FAST/MED responses, Gemma checks if the answer is complete and, if not, handles simple follow-ups locally instead of sending them back to Claude
- **Route more to LOCAL:** Better context awareness (knowing what the user just asked) could let Gemma handle follow-up questions itself rather than escalating them

**Guidance:** Start with pre-processing only — it's the lowest-risk change. Before `call_claude()`, run a quick `gemma.guide(message, system=REWRITE_PROMPT)` that sharpens the prompt. The token cost of the Gemma call is zero; if it saves even one Claude round trip it pays for itself. Track whether rewritten prompts correlate with fewer follow-up messages.

---

### 3. Reduce Second Brain (saltshaker) Input to Gemma

**Current state:** The full `saltshaker.md` is injected into every classify call as part of the context prompt. As the profile grows (up to 300 words), it adds ~75 tokens to every single classification — even for messages where the profile is irrelevant (e.g. "hi").

**The problem:** Gemma's classify prompt is already ~230 tokens (PEPPER.md) + profile + message. With a full profile this is ~310-350 tokens per call. On a 2B model, every token in the prompt has a cost in both latency and quality — the model's attention is split across everything it sees.

**Guidance:** Two approaches, both can be combined:
1. **Message-relevance filter:** Before injecting the full profile, have a lightweight check — if the message is short (< 10 words) and matches a LOCAL pattern (greeting, ack, simple Q), skip the profile injection entirely. Most LOCAL-tier messages don't benefit from personalisation anyway.
2. **Profile compression:** When `update_saltshaker()` runs, add an instruction to Gemma: "also output a 2-3 bullet FAST_FACTS section at the top — the highest-signal routing facts only." Inject only `FAST_FACTS` for classify, inject the full profile only for end-of-session update. This keeps the classify prompt tight.

---

### 4. Second Brain Should Be Evolving but Size-Limited

**Current state:** `saltshaker.md` grows freely up to 300 words (a soft instruction to Gemma, not enforced in code). There's no eviction of old information, no recency weighting, and no signal about which profile facts actually influenced routing decisions.

**The problem:** An ever-growing profile that Gemma rewrites holistically each session risks two failure modes — it drifts toward the most recent session's topics and loses older domain knowledge, or it accumulates noise as Gemma tries to preserve everything.

**Guidance:**
- **Hard size limit in code:** After `update_saltshaker()` writes the new profile, enforce a max character count (e.g. 1500 chars). If the new profile exceeds it, run a second Gemma call: "compress this profile to under 1500 characters, keeping the highest-signal routing facts and dropping anything older or redundant."
- **Recency header:** Prepend a small `## Recent Focus (last session)` section (3-5 bullets max) that Gemma fills with this session's dominant topics. The classifier sees this first and gives it more weight. Older content below the fold stays available but doesn't dominate.
- **Negative signal:** When the user presses `d` to downgrade a tier, record it as `[DOWNGRADE: MED→FAST] message` in the session log. `update_saltshaker()` already processes the session log — Gemma will naturally learn to route that message type lower next time.

---

## Known Issues

1. **Confidence is uncalibrated** — self-reported by a 2B model. No fix without logprob access or a trained classifier.

2. **No negative feedback loop** — manual downgrade (`d`) is not recorded as a signal. The profile update has no way to learn that a tier was wrong.

3. **`Session.prune_old()`** — defined in history.py, never called at startup.

4. **No test for grinder pipeline** — the core classifier has zero test coverage.

5. **spicerack.yaml drift risk** — confidence floors and fallback chain are now in `tiers.py`. The yaml file is kept as documentation but will silently diverge if someone updates one and not the other.
