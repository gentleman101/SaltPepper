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
├── tiers.py                ← Single source of truth: ICON, COLOR, NAME, MODEL dicts
├── debug.py                ← /debug toggle + Rich panel. Gitignored.
├── __main__.py             ← python -m saltpepper entry
│
├── router/
│   ├── grinder.py          ← Core classifier. PEPPER.md + saltshaker → Gemma → spicerack floors.
│   │                          Also: update_saltshaker() (end-of-session), get_insights() (/insights)
│   └── prompts.py          ← SETUP_GUIDE_PROMPT, ERROR_DIAGNOSE_PROMPT, CLASSIFY_SYSTEM/USER
│                              (CLASSIFY_SYSTEM/USER no longer used — grinder builds its own prompt)
│
├── models/
│   ├── gemma.py            ← LiteRT engine singleton.
│   │                          classify_with_context(full_prompt) → 3-layer JSON parser
│   │                          guide(situation) → one-shot blocking call
│   │                          chat_stream() → token streaming for LOCAL responses
│   └── claude.py           ← subprocess wrapper for `claude` CLI (FAST/MED/HIGH)
│
├── kitchen/
│   ├── PEPPER.md           ← Gemma's routing constitution. Tier definitions, hard ceilings,
│   │                          confidence rules, 9 worked examples. Injected into every classify call.
│   └── spicerack.yaml      ← Model capability map: costs, context windows, strengths, hard limits,
│                              confidence floors, fallback chain. Read programmatically by grinder.py.
│
├── config/
│   ├── __init__.py         ← CONFIG = deep merge of defaults.yaml + ~/.saltpepper/config.yaml
│   └── defaults.yaml       ← Confidence floors, timeouts, pricing, session settings
│
├── context/
│   └── history.py          ← Session class: stores exchanges, formats for LiteRT/Claude,
│                              saves to ~/.saltpepper/sessions/<uuid>.json
│
└── tracker/
    └── savings.py          ← SavingsTracker: actual vs Opus-baseline cost, status bar formatting

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
     ├── Load PEPPER.md (constitution — cached, always fresh)
     ├── Load saltshaker.md (user profile — cached, invalidated on file change)
     └── Build full prompt:
         [PEPPER.md] + ---USER PROFILE--- + [saltshaker or placeholder] + message
     │
     ▼
gemma.classify_with_context(full_prompt)
     │  3-layer JSON parser: fence strip → brace extract → json.loads + validate
     └── returns {"tier", "confidence", "reasoning"}
     │
     ▼
Safety escalation (spicerack.yaml):
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
route_and_respond()
  LOCAL → gemma.chat_stream()
  FAST/MED/HIGH → claude.call_claude(model=haiku/sonnet/opus)
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
└── config.yaml                    ← Optional user overrides (deep-merged over defaults)
```

---

## Confidence Scoring — Important Caveat

The confidence number is **self-reported by Gemma** — not a probability, not logprobs, not calibrated. Gemma writes `0.88` because PEPPER.md told it to output a confidence score. There is no mathematical grounding.

The thresholds in `spicerack.yaml` are the real safety net. Confidence is directionally useful but not reliable at fine granularity (0.71 vs 0.73 is noise).

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

## Known Issues

1. **`CLASSIFY_SYSTEM` / `CLASSIFY_USER` in `prompts.py` are unused** — grinder builds its own prompt directly from PEPPER.md. Either delete them or wire them in.

2. **Confidence is uncalibrated** — self-reported by a 2B model. No fix without logprob access or a trained classifier.

3. **Profile reinforces bad early routing** — no negative feedback signal when a tier gives a wrong answer. Manual downgrade key (`d`) is the only correction mechanism and it's not recorded.

4. **`Session.prune_old()`** — defined in history.py, never called at startup.

5. **No test for grinder pipeline** — the core classifier has zero test coverage.

---

## Roadmap

- [ ] Write `test_grinder.py` — mock Gemma, test escalation logic, debug dict shape
- [ ] Delete or wire `CLASSIFY_SYSTEM`/`CLASSIFY_USER` from prompts.py
- [ ] Record manual downgrades as negative signals into saltshaker
- [ ] Hook `Session.prune_old()` into startup
- [ ] Explore logprob access in LiteRT for real confidence scoring
