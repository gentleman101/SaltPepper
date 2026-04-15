"""
Claude Code CLI interface.
Calls `claude --model <sonnet|opus> -p "prompt"` as a subprocess.
Streams stdout to the console in real time.
"""
import shutil
import subprocess
import threading

from rich.console import Console


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
    model: str,
    history: list,
    console: Console,
) -> tuple[str, int]:
    """
    Invoke `claude --model <model> -p <prompt>`, streaming stdout live.
    Returns (full_response_text, output_token_estimate).
    Raises RuntimeError on auth failure or missing CLI.
    """
    if not is_installed():
        raise RuntimeError(
            "claude CLI not found — install: npm install -g @anthropic-ai/claude-code"
        )

    prompt = _format_prompt(message, history)
    cmd    = ["claude", "--model", model, "-p", prompt]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,
        )

        # Drain stderr in background to prevent pipe deadlock
        stderr_buf: list[str] = []

        def _drain_stderr():
            stderr_buf.append(proc.stderr.read())

        t_err = threading.Thread(target=_drain_stderr, daemon=True)
        t_err.start()

        # Stream stdout
        response_parts: list[str] = []
        while True:
            chunk = proc.stdout.read(64)
            if not chunk:
                break
            console.print(chunk, end="", markup=False, highlight=False)
            response_parts.append(chunk)

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
        return response, len(response) // 4

    except FileNotFoundError:
        raise RuntimeError(
            "claude not found in PATH — install: npm install -g @anthropic-ai/claude-code"
        )
