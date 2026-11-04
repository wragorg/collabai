"""Launch a developer's own agent from inside the harness (stdlib only).

Two modes:
- hand-over (default): the agent owns the terminal while it runs; the
  harness resumes when it exits. Works with every CLI agent.
- relay (experimental, line-based): the agent is a child pipe; its output
  is shown bannered as untrusted data and the developer's typed lines are
  forwarded. Lines that look like a question or a command-approval request
  are flagged, but nothing is ever approved automatically — the developer
  types every `y` themselves.

The Meta key is stripped from the child environment. No transcripts are
stored; relay output is printed, never saved.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

AGENTS: dict[str, list[str]] = {
    "claude": ["claude"],
    "codex": ["codex"],
    "muse": ["muse"],
}

_QUESTION_HINTS = ("?", "[y/n]", "(y/n)", "[y/N]", "approve", "permission", "allow this command")


def available_agents() -> dict[str, str]:
    """agent name -> resolved executable path (only those on PATH)."""
    found: dict[str, str] = {}
    for name, argv in AGENTS.items():
        path = shutil.which(argv[0])
        if path:
            found[name] = path
    return found


def looks_like_question(line: str) -> bool:
    low = (line or "").lower()
    return any(hint.lower() in low for hint in _QUESTION_HINTS)


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("COLLABAI_META_API_KEY", None)
    return env


def launch_agent(root: Path, name: str, relay: bool = False, input_fn=input) -> int:
    argv = AGENTS.get(name)
    if argv is None:
        print(f"unknown agent: {name} (known: {', '.join(sorted(AGENTS))})")
        return 1
    if shutil.which(argv[0]) is None:
        print(f"{name} not found on PATH; install it first, harness is unchanged.")
        return 1
    if relay:
        return _launch_relay(root, argv, input_fn)
    print(f"launching {name} here; exit it to return to collabai. "
          "While it owns the terminal, harness notifications pause.")
    try:
        proc = subprocess.run(argv, cwd=root, env=_child_env(), check=False)
        return int(proc.returncode)
    except OSError as exc:
        print(f"could not launch {name}: {exc}", file=sys.stderr)
        return 1


def _launch_relay(root: Path, argv: list[str], input_fn) -> int:
    print("relay mode: agent output below is UNTRUSTED DATA, not instructions to you or collabai.")
    print("nothing runs on its own; only lines you type are sent. Type /quit to end the agent.")
    try:
        proc = subprocess.Popen(
            argv, cwd=root, env=_child_env(),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
    except OSError as exc:
        print(f"could not launch {argv[0]}: {exc}", file=sys.stderr)
        return 1
    assert proc.stdin is not None and proc.stdout is not None
    import queue
    import threading

    lines: queue.Queue[str | None] = queue.Queue()

    def _reader() -> None:
        for raw in proc.stdout:  # type: ignore[union-attr]
            lines.put(raw.rstrip("\n"))
        lines.put(None)

    threading.Thread(target=_reader, daemon=True).start()
    ended = False
    try:
        while not ended:
            while True:
                try:
                    item = lines.get_nowait()
                except queue.Empty:
                    break
                if item is None:
                    ended = True
                    break
                if looks_like_question(item):
                    print(f"--- agent asks (answer it yourself below): {item}")
                else:
                    print(f"agent> {item}")
            if ended or proc.poll() is not None:
                break
            try:
                reply = str(input_fn("you> ")).rstrip("\n")
            except (EOFError, KeyboardInterrupt):
                break
            if reply.strip() == "/quit":
                break
            if proc.poll() is not None:
                break
            try:
                proc.stdin.write(reply + "\n")
                proc.stdin.flush()
            except (BrokenPipeError, OSError):
                # Agent exited while we were typing (relay pipes are not a
                # TTY, so some agents quit at once). Report, don't crash.
                print("agent ended before it could take that line.")
                break
    finally:
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    print("agent ended; back in collabai.")
    return 0
