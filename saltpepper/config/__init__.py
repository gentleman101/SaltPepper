import yaml
from pathlib import Path

_DEFAULTS = Path(__file__).parent / "defaults.yaml"
_USER     = Path.home() / ".saltpepper" / "config.yaml"


def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def load() -> dict:
    cfg = yaml.safe_load(_DEFAULTS.read_text())
    if _USER.exists():
        user = yaml.safe_load(_USER.read_text())
        if isinstance(user, dict):
            _deep_merge(cfg, user)
    return cfg


CONFIG = load()
