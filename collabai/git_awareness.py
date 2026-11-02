"""Git awareness: explicit fetch only, relevance check against local memory.

Never commits, merges, pushes, resets, or rebases. Read-only plus fetch.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run(root: Path, *args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        return 127, str(exc)


def is_repo(root: Path) -> bool:
    code, _ = _run(root, "rev-parse", "--git-dir")
    return code == 0


def upstream(root: Path) -> str:
    code, out = _run(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if code != 0:
        return ""
    return out.strip().splitlines()[0] if out.strip() else ""


def do_fetch(root: Path) -> tuple[int, str]:
    if not is_repo(root):
        return 1, "not a git repository"
    code, out = _run(root, "fetch", "--prune")
    if code != 0:
        return code, f"fetch failed:\n{out.strip()}"
    return 0, "fetch complete"


def changed_since_upstream(root: Path) -> tuple[list[str], str]:
    up = upstream(root)
    if not up:
        return [], "no upstream configured"
    code, out = _run(root, "diff", "--name-only", f"HEAD...{up}")
    if code != 0:
        return [], out.strip() or "diff failed"
    files = [line.strip() for line in out.splitlines() if line.strip()]
    return files, ""
