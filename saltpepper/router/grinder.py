"""
grinder.py — Capability-aware message classifier.

Pipeline:
  1. Load PEPPER.md (cached) + saltshaker.md (mtime-checked) into a context string
  2. Ask Gemma: given my capabilities and this user's profile, what tier?
  3. Apply confidence floors from tiers.py as safety escalation
  4. Return {"tier", "confidence", "reasoning"}

Fallback: if Gemma fails for any reason, default to MED.
"""
import json
from functools import lru_cache
from pathlib import Path

from saltpepper import tiers as _tiers

# ── Paths ──────────────────────────────────────────────────────────────────────

_KITCHEN_DIR = Path(__file__).parent.parent / "kitchen"
_PEPPER_FILE = _KITCHEN_DIR / "PEPPER.md"
_SALTSHAKER  = Path.home() / ".saltpepper" / "kitchen" / "saltshaker.md"


# ── Static assets (loaded once) ──────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_pepper() -> str:
    """Read PEPPER.md — Gemma's routing constitution. Cached for session."""
    try:
        return _PEPPER_FILE.read_text()
    except Exception:
        return ""


def _load_saltshaker() -> str:
    """Read the user's profile. Returns empty string on first run."""
    try:
        return _SALTSHAKER.read_text() if _SALTSHAKER.exists() else ""
    except Exception:
        return ""


# ── Context assembly (mtime-cached) ──────────────────────────────────────────

_ctx_cache: str | None = None
_ctx_mtime: float = 0.0


def _get_context() -> str:
    """Assemble PEPPER.md + saltshaker.md. Re-reads only when profile changes."""
    global _ctx_cache, _ctx_mtime
    try:
        mtime = _SALTSHAKER.stat().st_mtime if _SALTSHAKER.exists() else 0.0
    except Exception:
        mtime = 0.0

    if _ctx_cache is None or mtime != _ctx_mtime:
        pepper  = _load_pepper()
        profile = _load_saltshaker()
        profile_section = (
            f"---USER PROFILE---\n{profile.strip()}\n---END PROFILE---"
            if profile.strip()
            else "---USER PROFILE---\n(No profile yet — use default thresholds.)\n---END PROFILE---"
        )
        _ctx_cache = f"{pepper}\n\n{profile_section}"
        _ctx_mtime = mtime

    return _ctx_cache


# ── Escalation ───────────────────────────────────────────────────────────────

def _check_escalation(tier: str, confidence: float) -> tuple[str, bool]:
    """If confidence < floor for this tier, escalate one step. Returns (new_tier, escalated)."""
    floor = _tiers.CONFIDENCE_FLOOR.get(tier, 0.0)
    if floor > 0 and confidence < floor:
        return _tiers.FALLBACK.get(tier, "MED"), True
    return tier, False


# ── Classification ─────────────────────────────────────────────────────────

_CLASSIFY_USER = (
    'Classify this message:\n\n"{message}"\n\n'
    'Respond with only the JSON object. No markdown.'
)


def classify_request(message: str, _debug: dict | None = None) -> dict:
    """
    Classify a message using Gemma + PEPPER.md + saltshaker.md.
    Returns {"tier": str, "confidence": float, "reasoning": str}.
    Always returns a valid tier — never raises.
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
            "profile_loaded":   bool(_ctx_cache and "---USER PROFILE---\n(" not in _ctx_cache),
            "bias_rules_fired": [],
        })

    # Safety escalation via tiers.py confidence floors
    new_tier, escalated = _check_escalation(tier, confidence)
    if escalated:
        if _debug is not None:
            _debug["bias_rules_fired"].append(
                f"{tier} conf {confidence:.2f} < {_tiers.CONFIDENCE_FLOOR[tier]} → {new_tier}"
            )
        tier = new_tier

    if _debug is not None:
        _debug["final_tier"]       = tier
        _debug["final_confidence"] = confidence

    return {"tier": tier, "confidence": confidence, "reasoning": reasoning}


# ── Profile management ────────────────────────────────────────────────────────

def update_saltshaker(session_exchanges: list) -> bool:
    """
    Ask Gemma to update the user profile based on this session's exchanges.
    Called at session end from cli.py. Returns True if updated.
    """
    if not session_exchanges:
        return False

    from saltpepper.models import gemma

    lines = []
    for ex in session_exchanges[-20:]:
        tier = ex.get("tier", "?")
        user = ex.get("user", "")[:120]
        lines.append(f"[{tier}] {user}")
    session_summary = "\n".join(lines)

    existing_profile = _load_saltshaker()
    prompt           = _build_update_prompt(session_summary, existing_profile)
    new_profile      = gemma.guide(prompt)

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
