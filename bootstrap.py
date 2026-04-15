#!/usr/bin/env python3
"""
SaltPepper Bootstrap
====================
Run this once on a fresh machine to get fully set up:

    python3 bootstrap.py

What it does:
  1. Checks Python version (3.10+)
  2. Creates a venv at .venv/ (handles externally-managed Python on macOS/Homebrew)
  3. Installs the saltpepper package + all dependencies into the venv
  4. Downloads the Gemma 4 E2B model (~1.5 GB) if not already present
  5. Verifies Claude Code (claude) is on PATH
  6. Launches saltpepper via the venv and adds `sp` / `saltpepper` shims to PATH
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

REPO_DIR  = Path(__file__).parent.resolve()
VENV_DIR  = REPO_DIR / ".venv"
VENV_BIN  = VENV_DIR / "bin"
VENV_PY   = VENV_BIN / "python"
VENV_PIP  = VENV_BIN / "pip"

# ── Step 1: Python version ─────────────────────────────────────────────────────

def check_python():
    if sys.version_info < (3, 10):
        err(f"Python 3.10+ required (you have {sys.version})")
        err("Install via: brew install python@3.12")
        sys.exit(1)
    ok(f"Python {sys.version_info.major}.{sys.version_info.minor}")

# ── Step 2: Create venv ────────────────────────────────────────────────────────

def ensure_venv():
    if VENV_PY.exists():
        ok(f"venv already exists ({VENV_DIR})")
        return
    info("Creating virtual environment at .venv/ …")
    result = subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)])
    if result.returncode != 0:
        err("Failed to create venv")
        sys.exit(1)
    ok("venv created")

# ── Step 3: Install package ────────────────────────────────────────────────────

def install_package():
    info("Installing saltpepper + dependencies into venv (this may take a minute)…")
    result = subprocess.run(
        [str(VENV_PIP), "install", "-e", ".", "--quiet"],
        cwd=REPO_DIR,
    )
    if result.returncode != 0:
        err("pip install failed — check the output above")
        sys.exit(1)
    ok("Package installed")

    # Write global shim scripts so `sp` / `saltpepper` work from any terminal
    _write_shims()

def _write_shims():
    """
    Write thin wrapper scripts to ~/.local/bin/ so `sp` and `saltpepper`
    invoke the venv's Python regardless of working directory.
    """
    shim_dir = Path.home() / ".local" / "bin"
    shim_dir.mkdir(parents=True, exist_ok=True)

    venv_sp = VENV_BIN / "sp"
    if not venv_sp.exists():
        # Fallback: call module directly
        venv_sp = None

    for name in ("sp", "saltpepper"):
        shim = shim_dir / name
        if venv_sp:
            target = str(VENV_BIN / name)
            shim.write_text(f"#!/bin/sh\nexec {target} \"$@\"\n")
        else:
            shim.write_text(
                f"#!/bin/sh\nexec {VENV_PY} -m saltpepper \"$@\"\n"
            )
        shim.chmod(0o755)

    # Tell the user to add ~/.local/bin to PATH if it isn't already
    path_dirs = os.environ.get("PATH", "").split(":")
    if str(shim_dir) not in path_dirs:
        warn(f"Add this to your shell profile so `sp` works globally:")
        warn(f'  export PATH="$HOME/.local/bin:$PATH"')
        warn(f"  Then run: source ~/.zshrc  (or open a new terminal)")
    else:
        ok("`sp` and `saltpepper` available globally")

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

    # Run inside the venv so saltpepper + huggingface_hub are importable
    result = subprocess.run([
        str(VENV_PY), "-c",
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
    # Replace current process with the venv's sp entry point
    sp_bin = VENV_BIN / "sp"
    if sp_bin.exists():
        os.execv(str(sp_bin), [str(sp_bin)])
    else:
        os.execv(str(VENV_PY), [str(VENV_PY), "-m", "saltpepper"])

# ── Entry ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(BANNER)

    print(f"{BOLD}Step 1/5  Python version{RESET}")
    check_python()
    print()

    print(f"{BOLD}Step 2/5  Virtual environment{RESET}")
    ensure_venv()
    print()

    print(f"{BOLD}Step 3/5  Install package{RESET}")
    install_package()
    print()

    print(f"{BOLD}Step 4/5  Model{RESET}")
    ensure_model()
    print()

    print(f"{BOLD}Step 5/5  Claude Code{RESET}")
    check_claude()
    print()

    print(f"  {GREEN}{BOLD}All good. Launching SaltPepper.{RESET}")
    launch()
