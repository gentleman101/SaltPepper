#!/usr/bin/env python3
"""
SaltPepper — Intelligent Claude Code Router
Powered by Gemma 4 E2B (local) · Claude Sonnet · Claude Opus
"""
import select
import sys

from rich.console import Console
from rich.rule import Rule
from rich.text import Text

from saltpepper.router.classifier import classify_request
from saltpepper.models.gemma import (
    is_model_pulled,
    pull_model,
    chat_stream,
)
from saltpepper.models.claude import call_claude, is_installed as claude_installed
from saltpepper.context.history import Session
from saltpepper.tracker.savings import SavingsTracker
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
[/bold red][dim]  Intelligent Claude Code Router · Powered by Gemma 4 E2B[/dim]
"""

TIER_ICON  = {"LOW": "⚡", "MED": "⚖️ ", "HIGH": "🧠"}
TIER_COLOR = {"LOW": "green", "MED": "yellow", "HIGH": "red"}
TIER_MODEL = {"LOW": "Gemma", "MED": "Sonnet", "HIGH": "Opus"}
_DOWNGRADE = {"HIGH": "MED", "MED": "LOW"}


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

    if verb in ("/low", "/med", "/high"):
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
            icon = TIER_ICON.get(ex["tier"], "·")
            console.print(f"[dim]{icon} You:[/dim] {ex['user'][:90]}")

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

    elif verb == "/memory":
        parts = cmd.strip().split()
        sub   = parts[1].lower() if len(parts) > 1 else "status"

        if sub == "status":
            from saltpepper.router.vector_classifier import _user_bank_size, _get_bank_limit, is_learning
            size  = _user_bank_size()
            limit = _get_bank_limit()
            state = "[green]learning[/green]" if is_learning() else "[dim]complete[/dim]"
            console.print(f"[dim]Memory: {size}/{limit} examples  {state}[/dim]")

        elif sub == "reset":
            from saltpepper.router.vector_classifier import reset_user_bank
            reset_user_bank()
            console.print("[dim]↳ user memory cleared — learning restarted[/dim]")

        elif sub == "limit" and len(parts) > 2:
            try:
                n = int(parts[2])
                from saltpepper.router.vector_classifier import set_limit
                set_limit(n)
                console.print(
                    f"[dim]↳ bank limit set to {n} "
                    f"(session only — edit config.yaml to persist)[/dim]"
                )
            except ValueError:
                console.print("[dim]usage: /memory limit <number>[/dim]")
        else:
            console.print("[dim]usage: /memory status | reset | limit <N>[/dim]")

    elif verb in ("/quit", "/exit", "/q"):
        return False

    elif verb == "/help":
        _print_help()

    else:
        console.print(f"[dim]Unknown: {verb} — /help for commands[/dim]")

    return True


def _print_stats(tracker: SavingsTracker):
    stats = tracker.get_stats()
    msgs  = stats["messages"]
    console.print()
    console.print(Rule("[bold red]SaltPepper Stats 🌶️[/bold red]"))
    console.print(f"Messages: {msgs}")
    for tier in ("LOW", "MED", "HIGH"):
        count = stats["distribution"].get(tier, 0)
        pct   = int(count / msgs * 100) if msgs else 0
        console.print(
            f"  {TIER_ICON.get(tier, '·')} {tier:<4} "
            f"({TIER_MODEL.get(tier, tier):<7}): {count:>3}  ({pct}%)"
        )
    console.print()
    saved = stats["saved_tokens"]
    total = stats["baseline_tokens"]
    pct   = int(saved / total * 100) if total else 0
    console.print("Tokens:")
    console.print(f"  Baseline (all Opus):  {total:>10,}")
    console.print(f"  Actual API used:      {stats['actual_tokens']:>10,}")
    console.print(f"  Saved:                {saved:>10,}  ({pct}%)")
    console.print()
    console.print("Cost:")
    console.print(f"  Baseline:  ${stats['baseline_cost']:.4f}")
    console.print(f"  Actual:    ${stats['actual_cost']:.4f}")
    console.print(f"  Saved:     ${stats['saved_cost']:.4f}")
    console.print()


def _print_status(tracker: SavingsTracker, override_tier: str | None):
    stats = tracker.get_stats()
    mode  = "AUTO" if not override_tier else f"FORCED → {override_tier}"
    console.print()
    console.print(f"Routing:  {mode}")
    console.print(f"Messages: {stats['messages']}")
    console.print(f"Tokens:   {stats['actual_tokens']:,} used / {stats['saved_tokens']:,} saved")
    console.print()


def _print_help():
    console.print()
    console.print(Rule("[dim]Commands[/dim]"))
    for cmd, desc in [
        ("/low  /med  /high", "Force next request tier"),
        ("/auto",             "Return to auto routing"),
        ("/stats",            "Detailed token savings breakdown"),
        ("/status",           "Current routing + token counts"),
        ("/history",          "Recent conversation"),
        ("/clear",            "Clear session, reset counters"),
        ("/memory status",    "Show bank size and learning state"),
        ("/memory reset",     "Wipe user memory and restart learning"),
        ("/memory limit N",   "Set bank limit for this session"),
        ("/help",             "Show this help"),
        ("/debug",            "Toggle verbose routing debug panel"),
        ("/quit",             "Exit"),
    ]:
        console.print(f"  [bold cyan]{cmd:<22}[/bold cyan] {desc}")
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

    input_tok = len(message) // 4

    if tier == "LOW":
        msgs = session.get_messages_for_litert()
        msgs.append({"role": "user", "content": message})

        chunks: list[str] = []
        for chunk in chat_stream(msgs):
            console.print(chunk, end="", markup=False, highlight=False)
            chunks.append(chunk)
        console.print()

        response   = "".join(chunks)
        output_tok = len(response) // 4
        saved      = tracker.record("LOW", input_tok, output_tok)

    else:
        if not claude_installed():
            console.print(
                "[yellow]claude CLI not installed — cannot route to paid models.[/yellow]\n"
                "  → npm install -g @anthropic-ai/claude-code && claude auth login\n"
            )
            return ""

        claude_model = "sonnet" if tier == "MED" else "opus"
        history      = session.get_recent_history(max_turns=5)

        try:
            response, output_tok = call_claude(message, claude_model, history, console)
        except RuntimeError as e:
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

    console.print()
    console.print("[dim]Type your message. /help for commands. Ctrl-C to exit.[/dim]")
    console.print()

    while True:
        try:
            raw = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye 🌶️[/dim]")
            session.save()
            break

        if not raw:
            continue

        if raw.startswith("/"):
            if not handle_command(raw, session, tracker, override):
                console.print("[dim]Goodbye 🌶️[/dim]")
                session.save()
                break
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

        if tier in ("MED", "HIGH"):
            tier = _prompt_downgrade(tier)
            if tier == "CANCEL":
                continue

        try:
            response = route_and_respond(raw, tier, session, tracker)
            if response:
                session.add_exchange(raw, response, tier)
        except Exception as exc:
            console.print(f"[red]Unexpected error: {exc}[/red]")
            console.print("[dim]Tip: /low /med /high to force a tier[/dim]")
