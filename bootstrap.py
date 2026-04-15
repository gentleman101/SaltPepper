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

# ── Step 4: Check claude CLI ───────────────────────────────────────────────────

def check_claude():
    if shutil.which("claude"):
        ok("Claude Code found on PATH")
    else:
        warn("claude not found on PATH")
        warn("Install from: https://claude.ai/code  (or: npm install -g @anthropic-ai/claude-code)")
        warn("SaltPepper will still run but HIGH-tier routing won't work until claude is installed.")

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
