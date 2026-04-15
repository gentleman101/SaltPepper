"""Vector similarity classifier + self-learning user bank."""
import json
import threading
from pathlib import Path

import numpy as np

from saltpepper.router.embedder import embed, cosine_sim

_SHARED_BANK        = Path(__file__).parent / "example_bank.json"
_USER_BANK          = Path.home() / ".saltpepper" / "user_bank.json"
_THRESHOLD_LEARNING = 0.80   # while user bank is growing — more Gemma fallbacks
_THRESHOLD_COMPLETE = 0.90   # once bank hits limit — fully personalized
_TOP_K              = 5
_save_lock          = threading.Lock()

# In-memory store: list of {text, tier, source?, embedding}
_entries: list[dict] = []

# Lazily read bank limit from config to avoid circular imports at module level
_BANK_LIMIT: int | None = None


def _get_bank_limit() -> int:
    global _BANK_LIMIT
    if _BANK_LIMIT is None:
        try:
            from saltpepper.config import CONFIG
            _BANK_LIMIT = CONFIG.get("memory", {}).get("bank_limit", 1000)
        except Exception:
            _BANK_LIMIT = 1000
    return _BANK_LIMIT


def set_limit(n: int) -> None:
    """Override bank limit for the current session."""
    global _BANK_LIMIT
    _BANK_LIMIT = max(1, n)


def _load_bank(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def _init() -> None:
    shared = _load_bank(_SHARED_BANK)
    user   = _load_bank(_USER_BANK)
    for e in shared:
        _entries.append({**e, "source": "shared", "embedding": embed(e["text"])})
    for e in user:
        _entries.append({**e, "embedding": embed(e["text"])})


_init()


def _user_bank_size() -> int:
    return sum(1 for e in _entries if e.get("source") == "user")


def is_learning() -> bool:
    return _user_bank_size() < _get_bank_limit()


def _threshold() -> float:
    return _THRESHOLD_LEARNING if is_learning() else _THRESHOLD_COMPLETE


def _save_to_user_bank(text: str, tier: str) -> None:
    """Append one entry to user_bank.json. Called from a background thread."""
    with _save_lock:
        existing = _load_bank(_USER_BANK)
        if len(existing) >= _get_bank_limit():
            return
        _USER_BANK.parent.mkdir(parents=True, exist_ok=True)
        existing.append({"text": text, "tier": tier, "source": "user"})
        tmp = _USER_BANK.with_suffix(".tmp")
        tmp.write_text(json.dumps(existing, indent=2))
        tmp.rename(_USER_BANK)


def _notify_complete() -> None:
    try:
        from saltpepper.config import CONFIG
        if CONFIG.get("memory", {}).get("notify_complete", True):
            print("\n  \u2713 Memory complete \u2014 classifier fully personalized. Learning stopped.")
    except Exception:
        print("\n  \u2713 Memory complete \u2014 classifier fully personalized. Learning stopped.")


def learn(text: str, tier: str) -> None:
    """Add a Gemma-classified message to the in-memory bank and persist in background."""
    if _user_bank_size() >= _get_bank_limit():
        return
    entry = {"text": text, "tier": tier, "source": "user", "embedding": embed(text)}
    _entries.append(entry)
    threading.Thread(target=_save_to_user_bank, args=(text, tier), daemon=True).start()
    # Notify exactly once when the limit is crossed
    if _user_bank_size() >= _get_bank_limit():
        _notify_complete()


def reset_user_bank() -> None:
    """Wipe user_bank.json and remove user entries from in-memory store. Restarts learning."""
    global _entries
    with _save_lock:
        if _USER_BANK.exists():
            _USER_BANK.unlink()
    _entries = [e for e in _entries if e.get("source") != "user"]


def classify_by_vector(message: str) -> dict | None:
    """
    Returns {tier, confidence, top_match, max_sim} if similarity >= threshold, else None.
    Threshold adapts: 0.80 during learning phase, 0.90 after bank is complete.
    """
    if not _entries:
        return None

    try:
        msg_emb = embed(message)
    except Exception:
        return None

    scores = sorted(
        [(cosine_sim(msg_emb, e["embedding"]), e) for e in _entries],
        key=lambda x: x[0],
        reverse=True,
    )
    top = scores[:_TOP_K]

    if not top or top[0][0] < _threshold():
        return None

    votes: dict[str, float] = {}
    for sim, ex in top:
        votes[ex["tier"]] = votes.get(ex["tier"], 0.0) + sim

    tier  = max(votes, key=votes.__getitem__)
    total = sum(votes.values())
    return {
        "tier":       tier,
        "confidence": votes[tier] / total,
        "top_match":  top[0][1]["text"],
        "max_sim":    top[0][0],
    }
