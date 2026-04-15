#!/usr/bin/env python3
"""
SaltPepper — Intelligent Claude Code Router
Powered by you.
"""
import logging
import os
import re
import select
import sys
import warnings

# Silence HuggingFace "unauthenticated" advisory — not an error, just noise
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from saltpepper.router.grinder import classify_request, update_saltshaker, get_insights
from saltpepper.models.gemma import (
    is_model_pulled,
    pull_model,
    chat_stream,
    guide,
)
from saltpepper.models.claude import call_claude, is_installed as claude_installed
from saltpepper.context.history import Session
from saltpepper.tracker.savings import SavingsTracker, estimate_tokens
from saltpepper import tiers as _tiers
try:
    from saltpepper import debug as debug_mod
except ImportError:
    debug_mod = None

console = Console()

BANNER = """\
[bold red]
  ███████╗ █████╗ ██╗ ████████╗██████╗ ███████╗██████╗ ██████╗ ███████╗██████╗
  ██╔════╝██╔══██╗██║    ██║   ██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔════╝██╔══██╗
  ███████╗███████║██║    ██║   ██████╔╝█████╗  ██████╔╝██████╔╝█████╗  ██████╔╝
  ╚════██║██╔══██║██║    ██║   ██╔═══╝ ██╔══╝  ██╔═══╝ ██╔═══╝ ██╔══╝  ██╔══██╗
  ███████║██║  ██║███████╗██║   ██║     ███████╗██║     ██║     ███████╗██║  ██║
  ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝   ╚═╝     ╚══════╝╚═╝     ╚═╝     ╚══════╝╚═╝  ╚═╝
[/bold red][dim]  Intelligent Claude Code Router · Powered by you[/dim]
"""

# ── Error paste detection ──────────────────────────────────────────────────────

_ERROR_PATTERNS = re.compile(
    r"(Traceback \(most recent call last\)|"
    r"\w+Error:|\w+Exception:|"
    r"npm ERR!|ENOENT|"
    r"SyntaxError|PermissionError|ModuleNotFoundError|ImportError)",
    re.MULTILINE,
)

def _looks_like_error_paste(text: str) -> bool:
    """True for multi-line input containing error keywords — prevents false positives."""
    return "\n" in text and bool(_ERROR_PATTERNS.search(text))

TIER_ICON  = _tiers.ICON
TIER_COLOR = _tiers.COLOR
TIER_MODEL = _tiers.NAME
_DOWNGRADE = {"HIGH": "MED", "MED": "FAST", "FAST": "LOCAL"}


# ── Startup ────────────────────────────────────────────────────────────────────

def check_prerequisites() -> bool:
    if sys.version_info < (3, 10):
        console.print("[red]✗ Python 3.10+ required[/red]  → brew install python@3.12")
        return False

    if not is_model_pulled():
        console.print("[yellow]  First run: downloading Gemma 4 E2B (~1.5 GB)…[/yellow]")
        if pull_model():
            console.print("[green]  ✓ Gemma 4 E2B ready[/green]")
        else:
            console.print(
                "[red]  ✗ download failed[/red]\n"
                "  → huggingface-cli download litert-community/gemma-4-E2B-it-litert-lm"
                " gemma-4-E2B-it.litertlm --local-dir ~/.saltpepper/models"
            )
            return False

    if not claude_installed():
        console.print(
            "[yellow]  ⚠ claude CLI not found — MED/HIGH calls disabled[/yellow]\n"
            "  → npm install -g @anthropic-ai/claude-code && claude auth login"
        )

    return True


# ── Commands ───────────────────────────────────────────────────────────────────

def handle_command(cmd: str, session: Session, tracker: SavingsTracker,
                   override: list) -> bool:
    """Returns False when the user wants to quit."""
    verb = cmd.strip().split()[0].lower()

    if verb in ("/local", "/fast", "/med", "/high"):
        t = verb[1:].upper()
        override[0] = t
        console.print(f"[dim]↳ next request forced to [bold]{t}[/bold][/dim]")

    elif verb == "/auto":
        override[0] = None
        console.print("[dim]↳ routing returned to automatic[/dim]")

    elif verb == "/stats":
        _print_stats(tracker)

    elif verb == "/status":
        _print_status(tracker, override[0])

    elif verb == "/history":
        for ex in session.exchanges[-10:]:
            t     = ex.get("tier", "LOCAL")
            icon  = _tiers.ICON.get(t, "·")
            color = _tiers.COLOR.get(t, "dim")
            label = Text()
            label.append(f"{icon} {t}", style=f"bold {color}")
            label.append("  You: ", style="dim")
            label.append(ex["user"][:90])
            console.print(label)

    elif verb == "/clear":
        session.clear()
        tracker.reset()
        console.print("[dim]Session cleared.[/dim]")

    elif verb == "/debug":
        if debug_mod is None:
            console.print("[dim]debug module not available[/dim]")
        else:
            enabled = debug_mod.toggle()
            state   = "[bold yellow]ON[/bold yellow]" if enabled else "[dim]off[/dim]"
            console.print(f"[dim]↳ debug mode {state}[/dim]")

    elif verb == "/insights":
        console.print("[dim]↳ Gemma is reading your profile and session stats…[/dim]")
        summary = get_insights(tracker.get_stats())
        console.print()
        console.print(Panel(summary, title="🌶️  Insights", border_style="yellow", padding=(1, 2)))
        console.print()

    elif verb == "/account":
        _switch_account()

    elif verb in ("/quit", "/exit", "/q"):
        return False

    elif verb == "/help":
        _print_help()

    else:
        console.print(f"[dim]Unknown: {verb} — /help for commands[/dim]")

    return True


def _bar(pct: int, width: int = 20) -> str:
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _print_stats(tracker: SavingsTracker):
    stats = tracker.get_stats()
    msgs  = stats["messages"]

    console.print()
    console.print(Rule("[bold red]SaltPepper Stats 🌶️[/bold red]"))
    console.print()

    # ── Distribution ───────────────────────────────────────────────────────
    tbl = Table(show_header=True, header_style="bold dim",
                box=None, padding=(0, 1), expand=False)
    tbl.add_column("Tier",  style="bold", width=14)
    tbl.add_column("Model", style="dim",  width=8)
    tbl.add_column("Msgs",  justify="right", width=6)
    tbl.add_column("Share", justify="right", width=7)
    tbl.add_column("",      width=22)

    for t in ("LOCAL", "FAST", "MED", "HIGH"):
        count = stats["distribution"].get(t, 0)
        pct   = int(count / msgs * 100) if msgs else 0
        icon  = _tiers.ICON.get(t, "·")
        color = _tiers.COLOR.get(t, "white")
        model = _tiers.NAME.get(t, t)
        tbl.add_row(
            f"[{color}]{icon} {t}[/{color}]",
            model,
            str(count),
            f"{pct}%",
            f"[{color}]{_bar(pct)}[/{color}]",
        )
    console.print(tbl)
    console.print()

    # ── Tokens ─────────────────────────────────────────────────────────────
    saved = stats["saved_tokens"]
    total = stats["baseline_tokens"]
    pct   = int(saved / total * 100) if total else 0
    tok_tbl = Table(show_header=False, box=None, padding=(0, 1), expand=False)
    tok_tbl.add_column(style="dim", width=26)
    tok_tbl.add_column(justify="right", width=12)
    tok_tbl.add_column(style="dim", width=10)
    tok_tbl.add_row("[bold]Tokens[/bold]", "", "")
    tok_tbl.add_row("  Baseline (all Opus)", f"{total:,}",                "")
    tok_tbl.add_row("  Actual API used",     f"{stats['actual_tokens']:,}", "")
    tok_tbl.add_row("  Saved",               f"{saved:,}",                 f"({pct}%)")
    console.print(tok_tbl)
    console.print()

    # ── Cost ───────────────────────────────────────────────────────────────
    cost_tbl = Table(show_header=False, box=None, padding=(0, 1), expand=False)
    cost_tbl.add_column(style="dim", width=12)
    cost_tbl.add_column(justify="right", width=10)
    cost_tbl.add_row("[bold]Cost[/bold]", "")
    cost_tbl.add_row("  Baseline", f"${stats['baseline_cost']:.4f}")
    cost_tbl.add_row("  Actual",   f"${stats['actual_cost']:.4f}")
    cost_tbl.add_row("  Saved",    f"${stats['saved_cost']:.4f}")
    console.print(cost_tbl)
    console.print()


def _print_status(tracker: SavingsTracker, override_tier: str | None):
    stats = tracker.get_stats()
    if not override_tier:
        mode_text = Text("AUTO", style="bold green")
    else:
        mode_text = Text(f"FORCED → {override_tier}", style="bold yellow")

    body = Text.assemble(
        ("Routing:   ", "dim"), mode_text, "\n",
        ("Messages:  ", "dim"), (str(stats["messages"]), "bold"), "\n",
        ("Tokens:    ", "dim"),
        (f"{stats['actual_tokens']:,} used", "bold"),
        ("  /  ", "dim"),
        (f"{stats['saved_tokens']:,} saved", "bold green"),
    )
    console.print()
    console.print(Panel(body, title="[dim]Status[/dim]", border_style="dim", padding=(0, 2)))
    console.print()


def _switch_account():
    """Run `claude auth login` interactively to login or switch Claude account."""
    import subprocess as _sp
    import shutil as _sh
    if not _sh.which("claude"):
        console.print("[red]claude CLI not installed — cannot switch account[/red]")
        return
    console.print("[dim]Opening Claude login…[/dim]")
    result = _sp.run(["claude", "auth", "login"])
    if result.returncode == 0:
        # Show who we're now logged in as
        status = _sp.run(["claude", "auth", "status"], capture_output=True, text=True)
        for line in status.stdout.splitlines():
            if line.strip():
                console.print(f"[green]✓[/green] {line.strip()}")
    else:
        console.print("[yellow]Login cancelled or failed[/yellow]")


def _print_help():
    console.print()
    console.print(Rule("[dim]Commands[/dim]"))
    console.print()

    tbl = Table(show_header=False, box=None, padding=(0, 2), expand=False)
    tbl.add_column(style="bold cyan", width=30, no_wrap=True)
    tbl.add_column(style="dim")

    for cmd, desc in [
        ("/local  /fast  /med  /high", "Force next request to a specific tier"),
        ("/auto",                       "Return to automatic routing"),
        ("", ""),
        ("/insights",                   "Gemma's analysis of your usage patterns"),
        ("/stats",                      "Detailed token savings breakdown"),
        ("/status",                     "Current routing + token counts"),
        ("/history",                    "Recent conversation"),
        ("", ""),
        ("/clear",                      "Clear session, reset counters"),
        ("/account",                    "Login or switch Claude account"),
        ("/debug",                      "Toggle verbose routing debug panel"),
        ("", ""),
        ("/help",                       "Show this help"),
        ("/quit",                       "Exit"),
    ]:
        tbl.add_row(cmd, desc)

    console.print(tbl)
    console.print()


# ── Downgrade prompt ───────────────────────────────────────────────────────────

def _prompt_downgrade(tier: str) -> str:
    """
    Show a 5-second timeout prompt for MED/HIGH routing.
    Returns the final tier, or "CANCEL" if the user aborts.

    Edge cases handled:
      - Non-interactive terminal (piped input)   → skip, return tier
      - KeyboardInterrupt during prompt          → return tier unchanged
      - User types invalid input                 → treated as Y, proceed
      - LOW tier passed in                       → returns tier unchanged (guard)
    """
    if not sys.stdin.isatty():
        return tier

    lower = _DOWNGRADE.get(tier)
    if lower is None:
        return tier

    icon  = TIER_ICON[tier]
    model = TIER_MODEL[tier]
    console.print(
        f"[dim]↳ {icon} {tier} → {model}  confirm? "
        f"[bold]Y[/bold]=proceed  [bold]d[/bold]=downgrade to {lower}  [bold]n[/bold]=cancel  (5s)[/dim]",
        end=" ",
    )

    try:
        ready, _, _ = select.select([sys.stdin], [], [], 5.0)
        if not ready:
            console.print("[dim](proceeding)[/dim]")
            return tier
        key = sys.stdin.readline().strip().lower()
    except (KeyboardInterrupt, OSError):
        console.print()
        return tier

    if key in ("n", "no"):
        console.print("[dim]cancelled[/dim]")
        return "CANCEL"
    if key in ("d", "down"):
        console.print(f"[dim]downgraded → {lower}[/dim]")
        return lower
    # Y, Enter, or anything else → proceed
    console.print()
    return tier


# ── Routing ────────────────────────────────────────────────────────────────────

def route_and_respond(message: str, tier: str,
                      session: Session, tracker: SavingsTracker) -> str:
    icon  = TIER_ICON.get(tier, "·")
    color = TIER_COLOR.get(tier, "white")
    model = TIER_MODEL.get(tier, tier)

    console.print(f"\n[dim]↳ {icon} routing to [bold {color}]{model}[/bold {color}]…[/dim]\n")

    input_tok = estimate_tokens(message)

    if tier == "LOCAL":
        msgs = session.get_messages_for_litert()
        msgs.append({"role": "user", "content": message})

        chunks: list[str] = []
        with console.status("[dim]Gemma…[/dim]", spinner="dots"):
            for chunk in chat_stream(msgs):
                chunks.append(chunk)

        response   = "".join(chunks)
        output_tok = estimate_tokens(response)
        saved      = tracker.record("LOCAL", input_tok, output_tok)
        console.print(Markdown(response))
        console.print()

    else:
        if not claude_installed():
            console.print(
                "[yellow]claude CLI not installed — cannot route to paid models.[/yellow]\n"
                "  → npm install -g @anthropic-ai/claude-code && claude auth login\n"
            )
            return ""

        history = session.get_recent_history(max_turns=5)

        try:
            response, output_tok = call_claude(message, tier, history, console)
        except RuntimeError as e:
            err_str = str(e).lower()
            if "auth" in err_str or "login" in err_str or "401" in err_str or "unauthorized" in err_str:
                console.print("\n[yellow]⚠ Claude authentication required.[/yellow]")
                console.print("[dim]  Type /account to login, then resend your message.[/dim]\n")
            else:
                console.print(f"\n[red]Error: {e}[/red]\n")
            return ""

        console.print()
        saved = tracker.record(tier, input_tok, output_tok)

    # Per-message badge + status bar
    saved_str = f"saved {saved:,} tok" if saved > 0 else "—"
    badge = Text()
    badge.append(f"{icon} {tier} → {model}", style=f"bold {color}")
    badge.append(f" · {saved_str}", style="dim")
    console.print(badge)
    console.print(Rule(tracker.format_status_bar(), style="dim"))

    return response


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    console.print(BANNER)

    if not check_prerequisites():
        sys.exit(1)

    session  = Session()
    tracker  = SavingsTracker()
    override = [None]

    descs = {
        "LOCAL": "offline · free · instant",
        "FAST":  "fast + cheap · quick tasks",
        "MED":   "balanced · most coding work",
        "HIGH":  "most capable · complex reasoning",
    }
    tier_lines = Text()
    for t in _tiers.TIERS:
        icon  = _tiers.ICON[t]
        name  = _tiers.NAME[t]
        color = _tiers.COLOR[t]
        tier_lines.append(f"  {icon} ", style="bold")
        tier_lines.append(f"{name:<8}", style=f"bold {color}")
        tier_lines.append(f"  {descs[t]}\n", style="dim")
    footer = Text("\n  /help for all commands · Ctrl-C or /quit to exit", style="dim")
    console.print(Panel(Text.assemble(tier_lines, footer),
                        border_style="dim red", padding=(0, 1)))
    console.print()

    while True:
        try:
            raw = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Updating your profile… 🌶️[/dim]")
            update_saltshaker(session.exchanges)
            session.save()
            console.print("[dim]Goodbye.[/dim]")
            break

        if not raw:
            continue

        if raw.startswith("/"):
            if not handle_command(raw, session, tracker, override):
                console.print("[dim]Updating your profile… 🌶️[/dim]")
                update_saltshaker(session.exchanges)
                session.save()
                console.print("[dim]Goodbye.[/dim]")
                break
            continue

        # ── Error paste detection ──────────────────────────────────────────────
        if _looks_like_error_paste(raw):
            console.print("[dim]↳ ⚡ error paste detected — Gemma diagnosing…[/dim]")
            from saltpepper.router.prompts import ERROR_DIAGNOSE_PROMPT
            diagnosis = guide(raw, system_prompt=ERROR_DIAGNOSE_PROMPT)
            console.print()
            console.print(Panel(Markdown(diagnosis), title="[red]⚡ Diagnosis[/red]",
                                border_style="red", padding=(1, 2)))
            console.print()
            session.add_exchange(raw, diagnosis, "LOCAL")
            tracker.record("LOCAL", estimate_tokens(raw), estimate_tokens(diagnosis))
            continue

        if override[0]:
            tier        = override[0]
            override[0] = None
            console.print(f"[dim](forced: {tier})[/dim]")
        else:
            dbg    = {} if (debug_mod and debug_mod.DEBUG_ENABLED) else None
            result = classify_request(raw, _debug=dbg)
            tier   = result["tier"]
            if dbg is not None and debug_mod:
                debug_mod.panel(dbg)

        if tier in ("FAST", "MED", "HIGH"):
            tier = _prompt_downgrade(tier)
            if tier == "CANCEL":
                continue

        try:
            response = route_and_respond(raw, tier, session, tracker)
            if response:
                session.add_exchange(raw, response, tier)
        except Exception as exc:
            console.print(f"[red]Unexpected error: {exc}[/red]")
            console.print("[dim]Tip: /local /fast /med /high to force a tier[/dim]")
