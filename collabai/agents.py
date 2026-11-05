"""Launch a developer's own agent from inside the harness (stdlib only).

One supported mode: terminal hand-over. The agent owns the terminal while
it runs; the harness resumes when it exits. This works with every CLI
agent, including agents that require a TTY (notably ``claude``).

The earlier experimental line-relay mode was removed in 2.1.0: its pipes
are not a TTY, so TTY-requiring agents exited immediately, and presenting
it as a launch option was misleading. Hand-over is the professional path.

While an agent owns the terminal, harness notifications pause. As soon as
it exits, any agent questions that arrived in the meantime are surfaced
here so they are not missed.

The Meta key is stripped from the child environment. No transcripts are
stored.
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


def available_agents() -> dict[str, str]:
    """agent name -> resolved executable path (only those on PATH)."""
    found: dict[str, str] = {}
    for name, argv in AGENTS.items():
        path = shutil.which(argv[0])
        if path:
            found[name] = path
    return found


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("COLLABAI_META_API_KEY", None)
    return env


def _surface_pending(root: Path) -> None:
    """Flag questions that arrived while the agent owned the terminal."""
    try:
        from .notify import list_pending

        pending = list_pending(root)
    except Exception:
        return
    if pending:
        agents = ", ".join(sorted({str(r.get("agent", "agent")) for r in pending}))
        print(f"\a{len(pending)} agent question(s) waiting from {agents}: "
              "pick 2 (Inbox) in the harness, or run: collabai inbox")


def launch_agent(root: Path, name: str) -> int:
    argv = AGENTS.get(name)
    if argv is None:
        print(f"unknown agent: {name} (known: {', '.join(sorted(AGENTS))})")
        return 1
    if shutil.which(argv[0]) is None:
        print(f"{name} not found on PATH; install it first, harness is unchanged.")
        return 1
    print(f"launching {name} here; exit it to return to collabai. "
          "While it owns the terminal, harness notifications pause.")
    try:
        proc = subprocess.run(argv, cwd=root, env=_child_env(), check=False)
        code = int(proc.returncode)
    except OSError as exc:
        print(f"could not launch {name}: {exc}", file=sys.stderr)
        return 1
    _surface_pending(root)
    return code
