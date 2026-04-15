"""
grinder.py — Capability-aware message classifier.

Replaces vector_classifier + embedder entirely.
Gemma reads PEPPER.md (constitution) + saltshaker.md (user profile)
and classifies each message to the minimum viable tier.

Pipeline:
  1. Load PEPPER.md + saltshaker.md into a context string (cached per session)
  2. Ask Gemma: given my capabilities and this user's profile, what tier?
  3. Apply spicerack.yaml confidence floors as safety escalation
  4. Return {"tier", "confidence", "reasoning"}

Fallback: if Gemma fails for any reason, default to MED (never LOCAL or HIGH blind).
"""
import json
import re
from functools import lru_cache
from pathlib import Path

import yaml

# ── Paths ──────────────────────────────────────────────────────────────────────

_KITCHEN_DIR  = Path(__file__).parent.parent / "kitchen"
_PEPPER_FILE  = _KITCHEN_DIR / "PEPPER.md"
_SPICERACK    = _KITCHEN_DIR / "spicerack.yaml"
_SALTSHAKER   = Path.home() / ".saltpepper" / "kitchen" / "saltshaker.md"

# Valid tiers in this system
VALID_TIERS = ("LOCAL", "FAST", "MED", "HIGH")

# ── Spicerack (loaded once) ────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_spicerack() -> dict:
    try:
        return yaml.safe_load(_SPICERACK.read_text())
    except Exception:
        return {"escalation": {"LOCAL_to_FAST": 0.72, "FAST_to_MED": 0.65, "MED_to_HIGH": 0.60}}


def _confidence_floor(tier: str) -> float:
    rack = _load_spicerack()
    key_map = {
        "LOCAL": "LOCAL_to_FAST",
        "FAST":  "FAST_to_MED",
        "MED":   "MED_to_HIGH",
    }
    key = key_map.get(tier)
    if key is None:
        return 0.0
    return rack.get("escalation", {}).get(key, 0.60)


def _next_tier(tier: str) -> str:
    rack = _load_spicerack()
    return rack.get("fallback_chain", {}).get(tier, "MED")


# ── Context assembly ───────────────────────────────────────────────────────────

def _load_pepper() -> str:
    """Read PEPPER.md — Gemma's routing constitution."""
    try:
        return _PEPPER_FILE.read_text()
    except Exception:
        return ""


def _load_saltshaker() -> str:
    """Read the user's profile. Returns empty string on first run."""
    try:
        if _SALTSHAKER.exists():
            return _SALTSHAKER.read_text()
        return ""
    except Exception:
        return ""


def _build_classify_context() -> str:
    """
    Assemble the full context Gemma receives before every classification.
    PEPPER.md is the constitution; saltshaker.md is injected under its marker.
    Result is cached for the session — profile updates take effect next session.
    """
    pepper  = _load_pepper()
    profile = _load_saltshaker()

    profile_section = (
        f"---USER PROFILE---\n{profile.strip()}\n---END PROFILE---"
        if profile.strip()
        else "---USER PROFILE---\n(No profile yet — use default thresholds.)\n---END PROFILE---"
    )

    return f"{pepper}\n\n{profile_section}"


# Cache context for the session — re-read only if profile file changes
_ctx_cache: str | None = None
_ctx_mtime: float = 0.0

def _get_context() -> str:
    global _ctx_cache, _ctx_mtime
    try:
        mtime = _SALTSHAKER.stat().st_mtime if _SALTSHAKER.exists() else 0.0
    except Exception:
        mtime = 0.0

    if _ctx_cache is None or mtime != _ctx_mtime:
        _ctx_cache = _build_classify_context()
        _ctx_mtime = mtime

    return _ctx_cache


# ── Classification ─────────────────────────────────────────────────────────────

_CLASSIFY_USER = (
    'Classify this message:\n\n"{message}"\n\n'
    'Respond with only the JSON object. No markdown.'
)

def classify_request(message: str, _debug: dict | None = None) -> dict:
    """
    Classify a message using Gemma + PEPPER.md + saltshaker.md.

    Returns {"tier": str, "confidence": float, "reasoning": str}.
    Always returns a valid tier — never raises.

    _debug: if a dict is passed, intermediate state is written into it.
    """
    from saltpepper.models import gemma

    context  = _get_context()
    prompt   = f"{context}\n\n{_CLASSIFY_USER.format(message=message)}"

    raw_result = gemma.classify_with_context(prompt)

    tier       = raw_result.get("tier", "MED")
    confidence = raw_result.get("confidence", 0.0)
    reasoning  = raw_result.get("reasoning", "")

    if _debug is not None:
        _debug.update({
            "gemma_called":     True,
            "gemma_tier":       tier,
            "gemma_confidence": confidence,
            "gemma_reasoning":  reasoning,
            "profile_loaded":   bool(_load_saltshaker().strip()),
            "bias_rules_fired": [],
        })

    # Safety escalation using spicerack confidence floors
    floor = _confidence_floor(tier)
    if floor > 0 and confidence < floor:
        old_tier = tier
        tier     = _next_tier(tier)
        if _debug is not None:
            _debug["bias_rules_fired"].append(
                f"{old_tier} conf {confidence:.2f} < {floor} → {tier}"
            )

    if _debug is not None:
        _debug["final_tier"]       = tier
        _debug["final_confidence"] = confidence

    return {"tier": tier, "confidence": confidence, "reasoning": reasoning}


# ── Profile management ────────────────────────────────────────────────────────

def update_saltshaker(session_exchanges: list) -> bool:
    """
    Ask Gemma to update the user profile based on this session's exchanges.
    Called at session end from cli.py.

    Returns True if the profile was updated, False on failure.
    """
    if not session_exchanges:
        return False

    from saltpepper.models import gemma

    # Build a compact session summary for Gemma to reason over
    lines = []
    for ex in session_exchanges[-20:]:   # last 20 exchanges max
        tier = ex.get("tier", "?")
        user = ex.get("user", "")[:120]
        lines.append(f"[{tier}] {user}")
    session_summary = "\n".join(lines)

    existing_profile = _load_saltshaker()

    prompt = _build_update_prompt(session_summary, existing_profile)
    new_profile = gemma.guide(prompt)

    if not new_profile or new_profile.startswith("[Guidance unavailable"):
        return False

    _SALTSHAKER.parent.mkdir(parents=True, exist_ok=True)
    _SALTSHAKER.write_text(new_profile)

    # Invalidate context cache so next session picks up the new profile
    global _ctx_cache
    _ctx_cache = None

    return True


def _build_update_prompt(session_summary: str, existing_profile: str) -> str:
    existing_section = (
        f"Existing profile:\n{existing_profile.strip()}"
        if existing_profile.strip()
        else "Existing profile: (none — this is the first session)"
    )

    return f"""\
You are the memory layer of SaltPepper. After each session you update the user profile
(saltshaker.md) so future routing decisions are more accurate.

The profile is a concise markdown document that describes:
- The user's primary domains (e.g. "React/TypeScript frontend", "Python backend", "DevOps")
- Their typical question complexity per domain
- Routing patterns Gemma has noticed (e.g. "debugging questions in this domain are usually FAST")
- Any strong signals about what they do NOT need escalation for

Rules:
- Keep the profile under 300 words
- Be factual and specific — no fluff
- Preserve useful existing observations; update or remove stale ones
- Write in second-person: "You are a..." / "Your questions about X tend to be..."
- Output ONLY the updated profile markdown — no commentary, no fences

{existing_section}

This session's routing log (format: [TIER] user message):
{session_summary}

Write the updated profile now:"""


# ── Insights ──────────────────────────────────────────────────────────────────

def get_insights(tracker_stats: dict) -> str:
    """
    Ask Gemma to analyse this session's routing stats and the user profile,
    then return a plain-English insights summary.
    Used by the /insights command in cli.py.
    """
    from saltpepper.models import gemma

    profile = _load_saltshaker()
    stats   = json.dumps(tracker_stats, indent=2)

    prompt = f"""\
You are the analytics brain of SaltPepper. Given routing stats and the user profile,
give a short (5-8 line) insights summary in the SaltPepper voice (warm, slightly spicy).

Cover:
- Where most tokens are going and whether that's expected
- Any tier that seems overused based on the user's profile
- One concrete suggestion to save more tokens without quality loss
- One observation about what the user is working on

Session stats:
{stats}

User profile:
{profile.strip() if profile.strip() else "(none yet)"}

Write the insights now (plain text, no markdown headers, 5-8 lines max):"""

    return gemma.guide(prompt)
