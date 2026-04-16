"""
LiteRT / Gemma 4 E2B interface.
  - classify()    → route a message (single call, blocking)
  - chat_stream() → generate a response (token-streaming)
"""
import atexit
import json
import re
import shutil
from pathlib import Path
from typing import Generator

import litert_lm
from huggingface_hub import hf_hub_download

MODEL_DIR   = Path.home() / ".saltpepper" / "models"
MODEL_FILE  = MODEL_DIR / "gemma-4-E2B-it.litertlm"
HF_REPO     = "litert-community/gemma-4-E2B-it-litert-lm"
HF_FILENAME = "gemma-4-E2B-it.litertlm"

_engine: "litert_lm.Engine | None" = None


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def is_model_pulled() -> bool:
    return MODEL_FILE.exists()


def pull_model() -> bool:
    """Download the model from HuggingFace. Returns True on success."""
    try:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        print(f"\r  Downloading {HF_FILENAME} (~1.5 GB)…", flush=True)
        local_path = hf_hub_download(
            repo_id=HF_REPO,
            filename=HF_FILENAME,
            local_dir=str(MODEL_DIR),
        )
        # hf_hub_download may save to a cache subdir — copy to canonical path if needed
        dest = MODEL_FILE
        if not dest.exists() and local_path != str(dest):
            shutil.copy2(local_path, dest)
        print()
        return MODEL_FILE.exists()
    except Exception as e:
        print(f"\n  download error: {e}")
        return False


def _get_engine() -> "litert_lm.Engine":
    """Lazy-initialise the LiteRT engine singleton and register cleanup on exit."""
    global _engine
    if _engine is None:
        litert_lm.set_min_log_severity(litert_lm.LogSeverity.ERROR)
        cache_dir = MODEL_DIR / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        eng = litert_lm.Engine(
            str(MODEL_FILE),
            backend=litert_lm.Backend.CPU,
            cache_dir=str(cache_dir),
        )
        _engine = eng.__enter__()
        atexit.register(lambda: eng.__exit__(None, None, None))
    return _engine


# ── Classification ────────────────────────────────────────────────────────────

def classify_with_context(full_prompt: str) -> dict:
    """
    Capability-aware classification using a pre-assembled prompt.

    Called by grinder.py with the full context: PEPPER.md + saltshaker.md + message.
    Tiers: LOCAL | FAST | MED | HIGH

    Returns {"tier": str, "confidence": float, "reasoning": str}.
    Falls back to {"tier": "MED", "confidence": 0.0, "reasoning": "parse_error"} on any error.
    """
    _VALID = ("LOCAL", "FAST", "MED", "HIGH")

    try:
        engine = _get_engine()
        with engine.create_conversation() as conv:
            result = conv.send_message(full_prompt)
        raw = result["content"][0]["text"].strip()

        # Layer 1: strip markdown fences
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if fence:
            raw = fence.group(1)

        # Layer 2: extract first JSON object
        brace = re.search(r"\{.*\}", raw, re.DOTALL)
        if brace:
            raw = brace.group(0)

        # Layer 3: parse and validate
        data       = json.loads(raw)
        tier       = str(data.get("tier", "MED")).upper()
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
        if tier not in _VALID:
            tier = "MED"

        return {
            "tier":       tier,
            "confidence": confidence,
            "reasoning":  data.get("reasoning", ""),
        }

    except Exception:
        return {"tier": "MED", "confidence": 0.0, "reasoning": "parse_error"}


# ── One-shot guidance ─────────────────────────────────────────────────────────

def guide(situation: str, system_prompt: str | None = None) -> str:
    """
    One-shot blocking guidance call.

    Used by makeitsalty.py for setup guidance (SETUP_GUIDE_PROMPT) and by
    cli.py for error-paste diagnosis (ERROR_DIAGNOSE_PROMPT).

    `situation` is the user message — either a situation key like
    "claude_not_installed" or a raw error traceback pasted by the user.

    Returns the response text, or a plain fallback string on any error.
    """
    from saltpepper.router.prompts import SETUP_GUIDE_PROMPT

    sys_prompt = system_prompt if system_prompt is not None else SETUP_GUIDE_PROMPT

    try:
        engine = _get_engine()
        combined = f"{sys_prompt}\n\nUser: {situation}"
        with engine.create_conversation() as conv:
            result = conv.send_message(combined)
        return result["content"][0]["text"].strip()
    except Exception as e:
        return f"[Guidance unavailable: {e}]"


# ── Chat streaming ────────────────────────────────────────────────────────────

def _format_chat_prompt(messages: list) -> str:
    """Format a role/content message list into a single prompt string."""
    parts = []
    for m in messages:
        role = "User" if m["role"] == "user" else "Assistant"
        parts.append(f"{role}: {m['content']}")
    return "\n".join(parts)


def chat_stream(messages_or_prompt, timeout: int = 120) -> Generator[str, None, None]:
    """Stream a chat response from Gemma. Accepts a message list or pre-formatted prompt string."""
    try:
        engine = _get_engine()
        prompt = messages_or_prompt if isinstance(messages_or_prompt, str) else _format_chat_prompt(messages_or_prompt)
        with engine.create_conversation() as conv:
            for chunk in conv.send_message_async(prompt):
                for item in chunk.get("content", []):
                    if item.get("type") == "text" and item["text"]:
                        yield item["text"]
    except Exception as e:
        yield f"\n[LiteRT error: {e}]"
