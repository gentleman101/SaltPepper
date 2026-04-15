#!/usr/bin/env python3
"""
SaltPepper Bootstrap
====================
Run this once on a fresh machine to get fully set up:

    python3 bootstrap.py

What it does:
  1. Checks Python version (3.10+)
  2. Installs the saltpepper package + all dependencies
  3. Downloads the Gemma 4 E2B model (~1.5 GB) if not already present
  4. Verifies Claude Code (claude) is on PATH
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
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET}  {msg}")
def err(msg):  print(f"  {RED}✗{RESET}  {msg}")
def info(msg): print(f"  {CYAN}→{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}!{RESET}  {msg}")

BANNER = f"""{BOLD}{RED}
  ███████╗ █████╗ ██╗ ████████╗██████╗ ███████╗██████╗ ██████╗ ███████╗██████╗
  ██╔════╝██╔══██╗██║    ██║   ██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔════╝██╔══██╗
  ███████╗███████║██║    ██║   ██████╔╝█████╗  ██████╔╝██████╔╝█████╗  ██████╔╝
  ╚════██║██╔══██║██║    ██║   ██╔═══╝ ██╔══╝  ██╔═══╝ ██╔═══╝ ██╔══╝  ██╔══██╗
  ███████║██║  ██║███████╗██║   ██║     ███████╗██║     ██║     ███████╗██║  ██║
  ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝   ╚═╝     ╚══════╝╚═╝     ╚═╝     ╚══════╝╚═╝  ╚═╝
{RESET}{CYAN}  Intelligent Claude Code Router · Bootstrap{RESET}
"""

REPO_DIR = Path(__file__).parent.resolve()

# ── Step 1: Python version ─────────────────────────────────────────────────────

def check_python():
    if sys.version_info < (3, 10):
        err(f"Python 3.10+ required (you have {sys.version})")
        err("Install via: brew install python@3.12")
        sys.exit(1)
    ok(f"Python {sys.version_info.major}.{sys.version_info.minor}")

# ── Step 2: Install package ────────────────────────────────────────────────────

def install_package():
    info("Installing saltpepper + dependencies (this may take a minute)…")
    # --break-system-packages handles Homebrew / externally-managed Python on macOS
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".",
         "--quiet", "--break-system-packages"],
        cwd=REPO_DIR,
    )
    if result.returncode != 0:
        err("pip install failed — check the output above")
        sys.exit(1)
    ok("Package installed  (`sp` and `saltpepper` now available in your terminal)")

# ── Step 3: Pull model if missing ──────────────────────────────────────────────

MODEL_DIR  = Path.home() / ".saltpepper" / "models"
MODEL_FILE = MODEL_DIR / "gemma-4-E2B-it.litertlm"

def ensure_model():
    if MODEL_FILE.exists():
        ok(f"Model already present ({MODEL_FILE})")
        return

    warn("Gemma 4 E2B model not found — downloading (~1.5 GB)…")
    warn("This is a one-time download. Grab a coffee.")
    print()

    result = subprocess.run([
        sys.executable, "-c",
        "from saltpepper.models.gemma import pull_model; import sys; sys.exit(0 if pull_model() else 1)"
    ])
    if result.returncode != 0:
        err("Model download failed.")
        err("Check your internet connection or HuggingFace token (HF_TOKEN env var).")
        sys.exit(1)

    ok("Model downloaded")

# ── Step 4: Check claude CLI + auth ───────────────────────────────────────────

def check_claude():
    if not shutil.which("claude"):
        warn("claude not found on PATH")
        warn("Install: npm install -g @anthropic-ai/claude-code")
        warn("SaltPepper will still run but MED/HIGH routing won't work until claude is installed.")
        return

    ok("Claude Code found on PATH")

    # Check if already authenticated
    result = subprocess.run(
        ["claude", "auth", "status"],
        capture_output=True, text=True
    )
    already_auth = result.returncode == 0 and "logged in" in result.stdout.lower()

    if already_auth:
        # Extract account name if possible
        for line in result.stdout.splitlines():
            if "logged in" in line.lower() or "@" in line:
                ok(f"Claude authenticated  ({line.strip()})")
                return
        ok("Claude authenticated")
        return

    # Not authenticated — prompt to login
    print()
    warn("Claude is not authenticated. Login now to enable MED/HIGH routing.")
    print(f"  {CYAN}→{RESET}  Press Enter to open the Claude login page, or Ctrl+C to skip.")
    try:
        input()
    except KeyboardInterrupt:
        print()
        warn("Skipped. Run `claude auth login` later to enable MED/HIGH routing.")
        return

    subprocess.run(["claude", "auth", "login"])

    # Re-check after login attempt
    result2 = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True)
    if result2.returncode == 0 and "logged in" in result2.stdout.lower():
        ok("Claude authenticated")
    else:
        warn("Could not confirm authentication. Run `claude auth login` manually if needed.")

# ── Step 5: Launch ─────────────────────────────────────────────────────────────

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
    print()

    print(f"{BOLD}Step 4/4  Claude Code{RESET}")
    check_claude()
    print()

    print(f"  {GREEN}{BOLD}All good. Launching SaltPepper.{RESET}")
    launch()
