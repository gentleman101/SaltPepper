#!/usr/bin/env python3
"""
SaltPepper — makeitsalty.py
============================
Run this once on a fresh machine:

    python3 makeitsalty.py

What it does:
  1. Checks Python version (3.10+)
  2. Installs the saltpepper package + all dependencies
  3. Downloads the Gemma 4 E2B model (~1.5 GB)  ← Gemma wakes up here
  4. Verifies + authenticates Claude Code CLI    ← Gemma guides from here
  5. Launches saltpepper
"""
import os
import subprocess
import sys
import shutil
from pathlib import Path

# ── Colours (no deps needed) ──────────────────────────────────────────────────
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET}  {msg}")
def err(msg):  print(f"  {RED}✗{RESET}  {msg}")
def info(msg): print(f"  {CYAN}→{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}!{RESET}  {msg}")
def hr():      print(f"  {DIM}{'─' * 62}{RESET}")

BANNER = f"""{BOLD}{RED}
  ███████╗ █████╗ ██╗ ████████╗██████╗ ███████╗██████╗ ██████╗ ███████╗██████╗
  ██╔════╝██╔══██╗██║    ██║   ██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔════╝██╔══██╗
  ███████╗███████║██║    ██║   ██████╔╝█████╗  ██████╔╝██████╔╝█████╗  ██████╔╝
  ╚════██║██╔══██║██║    ██║   ██╔═══╝ ██╔══╝  ██╔═══╝ ██╔═══╝ ██╔══╝  ██╔══██╗
  ███████║██║  ██║███████╗██║   ██║     ███████╗██║     ██║     ███████╗██║  ██║
  ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝   ╚═╝     ╚══════╝╚═╝     ╚═╝     ╚══════╝╚═╝  ╚═╝
{RESET}{CYAN}  Intelligent Claude Code Router · Let's make it salty.{RESET}
"""

REPO_DIR  = Path(__file__).parent.resolve()
MODEL_DIR = Path.home() / ".saltpepper" / "models"
MODEL_FILE = MODEL_DIR / "gemma-4-E2B-it.litertlm"

# ── AI help prompt template ────────────────────────────────────────────────────

def _ai_help_block(context: str, error_snippet: str = "") -> str:
    """Returns a ready-to-paste block the user can drop into any AI chat."""
    snippet = f'\n  Error message: "{error_snippet}"' if error_snippet else ""
    return (
        f"\n  {DIM}── Paste this into any AI for help {'─' * 22}{RESET}\n"
        f"  I'm setting up SaltPepper on macOS and hit an error.\n"
        f"  Context: {context}{snippet}\n"
        f"  My Python: {sys.version.split()[0]}  |  OS: macOS\n"
        f"  How do I fix this?\n"
        f"  {DIM}{'─' * 62}{RESET}\n"
    )

# ── Pre-model error handlers (Gemma not yet available) ─────────────────────────

def _error_python_too_old():
    v = f"{sys.version_info.major}.{sys.version_info.minor}"
    print(f"\n  {RED}{BOLD}Python {v} is too fresh off the wrong vine.{RESET}")
    print(f"  SaltPepper needs Python 3.10 or newer.\n")
    print(f"  Here's the recipe:")
    print(f"    1.  brew install python@3.12")
    print(f"    2.  Close and reopen your terminal")
    print(f"    3.  python3 --version   (should show 3.12.x)")
    print(f"    4.  python3 makeitsalty.py")
    print(_ai_help_block("Python version too old", f"Python {v} < 3.10 required"))
    sys.exit(1)

def _error_pip_failed(stderr: str = ""):
    hint = stderr.strip().splitlines()[-1] if stderr.strip() else ""
    print(f"\n  {RED}{BOLD}The install hit a wall — pip couldn't get through.{RESET}")
    if hint:
        print(f"  Last error: {hint}\n")
    print(f"  Here's the recipe:")
    print(f"    1.  python3 -m pip install --upgrade pip")
    print(f"    2.  python3 -m pip install -e . --break-system-packages")
    print(f"    3.  If that fails, try: python3 -m pip install -e . --user")
    print(f"    4.  Last resort — use a venv:")
    print(f"          python3 -m venv .venv && source .venv/bin/activate")
    print(f"          pip install -e .")
    print(f"          python3 makeitsalty.py")
    print(_ai_help_block("pip install failed during SaltPepper setup", hint))
    sys.exit(1)

def _error_litert_import():
    print(f"\n  {RED}{BOLD}The package installed but litert_lm didn't make it to the table.{RESET}")
    print(f"  The LiteRT engine (needed to run Gemma) couldn't be imported.\n")
    print(f"  Here's the recipe:")
    print(f"    1.  pip uninstall litert-lm-api -y")
    print(f"    2.  pip install 'litert-lm-api>=0.10.1' --break-system-packages")
    print(f"    3.  python3 -c \"import litert_lm; print('ok')\"")
    print(f"    4.  python3 makeitsalty.py")
    print(_ai_help_block(
        "litert_lm import failed after pip install of litert-lm-api",
        "ImportError: No module named 'litert_lm'"
    ))
    sys.exit(1)

def _error_model_download(hint: str = ""):
    print(f"\n  {RED}{BOLD}The Gemma model download didn't make it through.{RESET}")
    if hint:
        print(f"  Hint: {hint}\n")
    print(f"  Here's the recipe:")
    print(f"    1.  Check your internet:  curl -I https://huggingface.co")
    print(f"    2.  Check free disk space: df -h ~   (need ~2 GB)")
    print(f"    3.  If HuggingFace needs a token:")
    print(f"          export HF_TOKEN=your_token_here")
    print(f"    4.  Try downloading manually:")
    print(f"          huggingface-cli download litert-community/gemma-4-E2B-it-litert-lm \\")
    print(f"            gemma-4-E2B-it.litertlm --local-dir ~/.saltpepper/models")
    print(f"    5.  python3 makeitsalty.py")
    print(_ai_help_block(
        "Gemma 4 E2B model download (~1.5 GB) from HuggingFace failed",
        hint or "download returned non-zero exit code"
    ))
    sys.exit(1)

# ── Step 1: Python version ─────────────────────────────────────────────────────

def check_python():
    if sys.version_info < (3, 10):
        _error_python_too_old()
    ok(f"Python {sys.version_info.major}.{sys.version_info.minor}")

# ── Step 2: Install package ────────────────────────────────────────────────────

def install_package():
    info("Installing saltpepper + dependencies (this may take a minute)…")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".",
         "--quiet", "--break-system-packages"],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _error_pip_failed(result.stderr)

    # Probe litert_lm — pip may succeed but the native lib can still be missing
    probe = subprocess.run(
        [sys.executable, "-c", "import litert_lm"],
        capture_output=True,
    )
    if probe.returncode != 0:
        _error_litert_import()

    ok("Package installed  (`sp` and `saltpepper` now available)")

# ── Step 3: Download model ─────────────────────────────────────────────────────

def ensure_model():
    if MODEL_FILE.exists():
        ok(f"Model already present")
        return

    warn("Gemma 4 E2B model not found — downloading (~1.5 GB)…")
    warn("One-time download. Grab a coffee.")
    print()

    result = subprocess.run([
        sys.executable, "-c",
        "from saltpepper.models.gemma import pull_model; import sys; sys.exit(0 if pull_model() else 1)"
    ])
    if result.returncode != 0:
        _error_model_download()

    ok("Model downloaded")

# ── Gemma guide (comes alive after model is ready) ────────────────────────────

_guide_ready = False

def _init_gemma_guide():
    """Warm the Gemma engine and print the handoff banner."""
    global _guide_ready
    try:
        info("Waking Gemma up…")
        from saltpepper.models.gemma import _get_engine
        _get_engine()
        _guide_ready = True
        print()
        hr()
        print(f"  {RED}{BOLD}🌶  Gemma is awake. I'll take it from here.{RESET}")
        hr()
        print()
    except Exception as e:
        warn(f"Gemma engine didn't start ({e}) — using plain messages.")

def _gemma_guide(situation: str):
    """Run a live Gemma guidance call if the engine is ready."""
    if not _guide_ready:
        return
    try:
        from saltpepper.models.gemma import guide
        print()
        response = guide(situation)
        # Print each line indented for readability
        for line in response.splitlines():
            print(f"  {line}")
        print()
    except Exception:
        pass  # silent fallback — caller's plain message already shown

# ── Step 4: Claude CLI + auth (Gemma-guided) ──────────────────────────────────

def check_claude():
    if not shutil.which("claude"):
        _gemma_guide("claude_not_installed")
        if not _guide_ready:
            warn("claude not found — install: npm install -g @anthropic-ai/claude-code")
            warn("MED/HIGH routing disabled until claude is installed.")
        return

    ok("Claude Code found on PATH")

    result = subprocess.run(
        ["claude", "auth", "status"],
        capture_output=True, text=True
    )
    already_auth = result.returncode == 0 and "logged in" in result.stdout.lower()

    if already_auth:
        for line in result.stdout.splitlines():
            if "logged in" in line.lower() or "@" in line:
                ok(f"Claude authenticated  ({line.strip()})")
                return
        ok("Claude authenticated")
        return

    # Not authenticated — Gemma guides, then open login
    _gemma_guide("claude_auth_needed")
    if not _guide_ready:
        warn("Claude not authenticated.")
        print(f"  {CYAN}→{RESET}  Press Enter to open the Claude login page, or Ctrl+C to skip.")

    try:
        input()
    except KeyboardInterrupt:
        print()
        warn("Skipped. Run `claude auth login` anytime, or type /account inside SaltPepper.")
        return

    subprocess.run(["claude", "auth", "login"])

    result2 = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True)
    if result2.returncode == 0 and "logged in" in result2.stdout.lower():
        ok("Claude authenticated")
    else:
        _gemma_guide("claude_auth_failed")
        if not _guide_ready:
            warn("Could not confirm auth. Run `claude auth login` manually if needed.")

# ── Launch ─────────────────────────────────────────────────────────────────────

def launch():
    print()
    info("Starting SaltPepper…")
    print()
    sp = shutil.which("sp")
    if sp:
        os.execv(sp, [sp])
    else:
        os.execv(sys.executable, [sys.executable, "-m", "saltpepper"])

# ── Entry ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(BANNER)

    print(f"{BOLD}Step 1/4  Python version{RESET}")
    check_python()
    print()

    print(f"{BOLD}Step 2/4  Install package{RESET}")
    install_package()
    print()

    print(f"{BOLD}Step 3/4  Model{RESET}")
    ensure_model()
    _init_gemma_guide()       # ← Gemma wakes up

    print(f"{BOLD}Step 4/4  Claude Code{RESET}")
    check_claude()
    print()

    print(f"  {GREEN}{BOLD}All good. Launching SaltPepper.{RESET}")
    launch()
