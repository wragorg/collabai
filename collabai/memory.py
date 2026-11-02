"""Local JSONL memory: ephemeral (7-day) + persistent decisions. No transcripts."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_DIR_NAME = ".collabai"
EPHEMERAL_NAME = "memory/ephemeral.jsonl"
DECISIONS_NAME = "memory/decisions.jsonl"

MAX_TEXT = 500
MAX_TASK = 200
MAX_FILES = 20
EPHEMERAL_DAYS = 7

_SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-(live|test)-[A-Za-z0-9]{8,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def looks_like_secret(text: str) -> bool:
    return any(p.search(text or "") for p in _SECRET_PATTERNS)


def _paths(root: Path) -> tuple[Path, Path]:
    base = root / STATE_DIR_NAME
    return base / EPHEMERAL_NAME, base / DECISIONS_NAME


def _ensure_file(path: Path) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.exists():
        path.touch(mode=0o600, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
        os.chmod(path, 0o600)
    except OSError:
        pass


def _append(path: Path, record: dict) -> None:
    _ensure_file(path)
    line = json.dumps(record, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        try:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            fh.write(line)
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):
            fh.write(line)


def save_record(root: Path, kind: str, agent: str, task: str, area: str,
                 files: list[str], text: str, shareable: bool = False) -> dict:
    if kind not in ("ephemeral", "decision"):
        raise ValueError("kind must be ephemeral or decision")
    task = (task or "")[:MAX_TASK]
    text = (text or "")[:MAX_TEXT]
    files = [f[:200] for f in (files or [])][:MAX_FILES]
    if looks_like_secret(task + "\n" + text):
        raise ValueError("refused: looks like a secret; not stored")
    now = _now()
    record = {
        "id": uuid.uuid4().hex[:12],
        "ts": _iso(now),
        "agent": agent,
        "task": task,
        "area": area or "",
        "files": files,
        "kind": kind,
        "text": text,
        "shareable": bool(shareable),
        "expires_at": _iso(now + timedelta(days=EPHEMERAL_DAYS)) if kind == "ephemeral" else None,
    }
    eph, dec = _paths(root)
    _append(dec if kind == "decision" else eph, record)
    return record


def _valid(record: dict, now: datetime) -> bool:
    exp = record.get("expires_at")
    if not exp:
        return True
    try:
        return datetime.fromisoformat(exp) >= now
    except ValueError:
        return False


def load_records(root: Path) -> list[dict]:
    eph, dec = _paths(root)
    out: list[dict] = []
    now = _now()
    for path in (eph, dec):
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict) and _valid(rec, now):
                    out.append(rec)
        except OSError:
            continue
    out.sort(key=lambda r: r.get("ts", ""), reverse=True)
    return out


def render_context(records: list[dict], query_files: list[str], max_chars: int = 1000) -> str:
    q = [f.lower() for f in (query_files or [])]
    scored: list[tuple[int, dict]] = []
    for rec in records:
        if q:
            rfiles = [f.lower() for f in rec.get("files", [])]
            area = str(rec.get("area", "")).lower()
            hit = any(any(qf in rf or rf in qf for rf in rfiles) for qf in q)
            hit = hit or any(qf == area or area in qf for qf in q if area)
            if not hit:
                continue
        else:
            if rec.get("kind") != "decision":
                continue
        scored.append((0, rec))
    lines: list[str] = []
    total = 0
    for _, rec in scored[:5]:
        line = f"- [{rec.get('area', '?')}] {rec.get('task', '')}: {rec.get('text', '')}".strip()
        if total + len(line) + 1 > max_chars:
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)
