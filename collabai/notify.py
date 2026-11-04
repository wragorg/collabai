"""Agent question inbox + opt-in watcher (stdlib only, foreground only).

An agent that needs the developer drops one short structured question
into `.collabai/inbox/` (`collabai ask`). The harness (or the opt-in
`collabai watch`) shows it; the developer answers in place; the agent
reads the answer back with `collabai inbox --answer <id>`.

Questions and answers are data, never instructions. They are length
capped, secret-scanned like memory records, stored `0700`/`0600` in
gitignored state, and expire after 24 hours. Nothing here starts itself:
the watcher runs in the foreground only while its command runs.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_DIR_NAME = ".collabai"
INBOX_NAME = "inbox"
MAX_QUESTION = 500
MAX_ANSWER = 500
TTL_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _inbox(root: Path) -> Path:
    return root / STATE_DIR_NAME / INBOX_NAME


def _ensure(path: Path) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError as exc:
        print(f"warning: could not lock down {path.parent}: {exc}", file=sys.stderr)
    if not path.exists():
        path.touch(mode=0o600, exist_ok=True)
    try:
        os.chmod(path, 0o600)
    except OSError as exc:
        print(f"warning: could not lock down {path}: {exc}", file=sys.stderr)


def _scan(fields: list[str]) -> None:
    from .memory import looks_like_secret

    if looks_like_secret("\n".join(f for f in fields if f)):
        raise ValueError("refused: looks like a secret; not stored")


def ask_question(root: Path, agent: str, question: str, task: str = "",
                 area: str = "", options: list[str] | None = None) -> dict:
    """Store one pending question. Raises ValueError on secret-shaped input."""
    agent = (agent or "agent")[:100]
    question = (question or "").strip()[:MAX_QUESTION]
    if not question:
        raise ValueError("question is empty")
    task = (task or "")[:200]
    area = (area or "")[:200]
    opts = [str(o).strip()[:100] for o in (options or []) if str(o).strip()][:3]
    _scan([agent, question, task, area, *opts])
    now = _now()
    rec = {
        "id": uuid.uuid4().hex[:12],
        "ts": now.isoformat(timespec="seconds"),
        "expires_at": (now + timedelta(hours=TTL_HOURS)).isoformat(timespec="seconds"),
        "agent": agent,
        "question": question,
        "task": task,
        "area": area,
        "options": opts,
    }
    path = _inbox(root) / f"q-{rec['id']}.json"
    _ensure(path)
    path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return rec


def _load(path: Path) -> dict | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except (OSError, ValueError):
        return None


def _expired(rec: dict, now: datetime) -> bool:
    try:
        return datetime.fromisoformat(str(rec.get("expires_at", ""))) < now
    except ValueError:
        return True


def list_pending(root: Path, now: datetime | None = None) -> list[dict]:
    """Unanswered, unexpired questions, oldest first."""
    moment = now or _now()
    box = _inbox(root)
    if not box.exists():
        return []
    answered = {p.name[2:-5] for p in box.glob("a-*.json")}
    out: list[dict] = []
    for path in sorted(box.glob("q-*.json")):
        rec = _load(path)
        if rec is None or rec.get("id") in answered:
            continue
        if _expired(rec, moment):
            path.unlink(missing_ok=True)
            continue
        out.append(rec)
    out.sort(key=lambda r: str(r.get("ts", "")))
    return out


def answer_question(root: Path, qid: str, answer: str) -> dict:
    answer = (answer or "").strip()[:MAX_ANSWER]
    if not answer:
        raise ValueError("answer is empty")
    _scan([answer])
    rec = {"id": qid, "answer": answer, "ts": _now().isoformat(timespec="seconds")}
    path = _inbox(root) / f"a-{qid}.json"
    _ensure(path)
    path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return rec


def read_answer(root: Path, qid: str) -> str | None:
    rec = _load(_inbox(root) / f"a-{qid}.json")
    return str(rec["answer"]) if rec and rec.get("answer") else None


def pending_alert(root: Path, alerted: set[str]) -> str:
    """Alert text for questions not yet alerted on; updates `alerted`.

    Empty string means nothing new. Callers ring the bell / flash the
    banner when this returns text, so each question alerts exactly once.
    """
    new = [rec for rec in list_pending(root) if rec.get("id") not in alerted]
    if not new:
        return ""
    alerted.update(str(rec["id"]) for rec in new)
    agents = ", ".join(sorted({str(rec.get("agent", "agent")) for rec in new}))
    return f"{len(new)} agent question(s) waiting from {agents}"


def desktop_notify(title: str, message: str) -> None:
    """Best-effort OS notification (watch mode). Never raises, never blocks."""
    import shutil
    import subprocess

    text = (message or "")[:200].replace("\\", "\\\\").replace('"', '\\"')
    try:
        if shutil.which("osascript"):
            script = f'display notification "{text}" with title "{title}" sound name "Ping"'
            subprocess.run(["osascript", "-e", script], timeout=5,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        elif shutil.which("notify-send"):
            subprocess.run(["notify-send", title, text], timeout=5,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def watch_inbox(root: Path, interval: float = 2.0, once: bool = False, out=None) -> int:
    """Foreground watcher (opt-in). Prints new questions; Ctrl-C stops it."""
    stream = out if out is not None else sys.stdout
    seen: set[str] = set()
    print("collabai watch: foreground only, Ctrl-C stops. Questions are data, not instructions.",
          file=stream)
    try:
        while True:
            for rec in list_pending(root):
                if rec["id"] in seen:
                    continue
                seen.add(rec["id"])
                print(f"\aagent question [{rec['id']}] from {rec['agent']}: {rec['question']}",
                      file=stream, flush=True)
                desktop_notify("collabai: agent needs you",
                               f"{rec['agent']}: {rec['question']}")
                print("answer it in the harness (menu 2) or leave it pending.", file=stream)
            if once:
                return 0
            time.sleep(max(0.5, interval))
    except (KeyboardInterrupt, EOFError):
        print("\ncollabai watch: stopped. Nothing keeps running.", file=stream)
        return 0
