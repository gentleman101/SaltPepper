"""
Claude Code CLI interface.
Calls `claude --model <model> -p --output-format stream-json` for real token streaming.

Tier → model mapping:
  FAST → claude-haiku-4-5-20251001
  MED  → claude-sonnet-4-6
  HIGH → claude-opus-4-6
"""
import json
import shutil
import subprocess
import threading

from rich.console import Console

from saltpepper import tiers as _tiers
from saltpepper.tracker.savings import estimate_tokens


def is_installed() -> bool:
    return shutil.which("claude") is not None


def _format_prompt(message: str, history: list) -> str:
    """Build a prompt string that includes recent conversation history."""
    if not history:
        return message

    lines = ["Previous conversation:", "---"]
    for ex in history[-5:]:
        lines.append(f"User: {ex['user']}")
        resp = ex["assistant"]
        if len(resp) > 600:
            resp = resp[:600] + "…"
        lines.append(f"Assistant: {resp}")
        lines.append("")
    lines += ["---", "", "Current message:", message]
    return "\n".join(lines)


def call_claude(
    message: str,
    tier: str,
    history: list,
    console: Console,
    model_override: str | None = None,
    on_delta: "callable | None" = None,
) -> tuple[str, int]:
    """
    Invoke claude CLI with stream-json output for real token-by-token streaming.
    Parses partial_json assistant text chunks and prints them as they arrive.

    Returns (full_response_text, output_token_estimate).
    Raises RuntimeError on auth failure or missing CLI.
    """
    if not is_installed():
        raise RuntimeError(
            "claude CLI not found — install: npm install -g @anthropic-ai/claude-code"
        )

    model  = model_override or _tiers.MODEL_ID.get(tier.upper(), _tiers.MODEL_ID["MED"])
    prompt = _format_prompt(message, history)
    cmd    = [
        "claude",
        "--model", model,
        "--output-format", "stream-json",
        "--include-partial-messages",
        "--verbose",
        "--no-session-persistence",
        "-p", prompt,
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,   # line-buffered — stream-json emits one JSON object per line
        )

        stderr_buf: list[str] = []

        def _drain_stderr():
            stderr_buf.append(proc.stderr.read())

        t_err = threading.Thread(target=_drain_stderr, daemon=True)
        t_err.start()

        response_parts: list[str] = []

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = event.get("type")

            # Streaming delta — content_block_delta carries the actual text chunks
            if etype == "stream_event":
                inner = event.get("event", {})
                if inner.get("type") == "content_block_delta":
                    delta = inner.get("delta", {}).get("text", "")
                    if delta:
                        response_parts.append(delta)
                        if on_delta:
                            on_delta(delta)
                        else:
                            console.print(delta, end="", markup=False, highlight=False)

            # Final result — fallback if no stream_event deltas were captured
            elif etype == "result":
                final = event.get("result", "")
                if final and not response_parts:
                    response_parts.append(final)
                    if on_delta:
                        on_delta(final)
                    else:
                        console.print(final, end="", markup=False, highlight=False)

        if not on_delta:
            console.print()   # newline after raw streaming completes
        proc.wait()
        t_err.join(timeout=3)

        if proc.returncode != 0:
            err = stderr_buf[0] if stderr_buf else ""
            if "auth" in err.lower() or "login" in err.lower() or "unauthorized" in err.lower():
                raise RuntimeError("Claude auth required — run: claude auth login")
            raise RuntimeError(
                f"claude exited {proc.returncode}: {err[:300] if err else '(no stderr)'}"
            )

        response = "".join(response_parts)
        return response, estimate_tokens(response)

    except FileNotFoundError:
        raise RuntimeError(
            "claude not found in PATH — install: npm install -g @anthropic-ai/claude-code"
        )
