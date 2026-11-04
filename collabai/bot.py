"""Terminal companion (Pip). Foreground only, stdlib only, metadata only.

Run on demand with `collabai bot`. It reads structured memory records and,
optionally, a running Live Share feed. It never reads transcripts, prompts,
diffs, or file contents, and it never sends anything across sessions itself.
Every cross-session move it suggests is printed for the human to run by hand.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SPINNER = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
SPINNER_ASCII = ("|", "/", "-", "\\")
PULSE = ("●", "◉")
FACES = {
    "clear": ("(•‿•)", "all clear"),
    "overlap": ("(⊙_⊙)", "overlap ahead"),
    "sleepy": ("(-_-)zZ", "quiet out there"),
    "celebrate": ("(^‿^)", "nice, one landed"),
}
STALE_MINUTES = 30
TABLE_WHO = 12
TABLE_AREA = 10
TABLE_TASK = 22


def spin_frame(tick: int, tty: bool = True) -> str:
    frames = SPINNER if tty else SPINNER_ASCII
    return frames[tick % len(frames)]


def pulse_dot(tick: int) -> str:
    return PULSE[tick % len(PULSE)]


def burst() -> str:
    return "* + *"


def typing_dots(tick: int) -> str:
    return "." * (tick % 3 + 1)


def _parse_ts(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def build_snapshot(records: list[dict]) -> dict:
    """Collapse newest-first records into agents, areas, decisions, overlaps."""
    agents: list[dict] = []
    seen: set[str] = set()
    decisions: list[dict] = []
    latest: datetime | None = None
    for rec in records:
        ts = _parse_ts(str(rec.get("ts", "")))
        if ts is not None and (latest is None or ts > latest):
            latest = ts
        if rec.get("kind") == "decision":
            decisions.append(rec)
        agent = str(rec.get("agent", "") or "unknown")
        if agent in seen:
            continue
        seen.add(agent)
        agents.append(
            {
                "agent": agent,
                "task": str(rec.get("task", "")),
                "area": str(rec.get("area", "")),
                "ts": str(rec.get("ts", "")),
                "kind": str(rec.get("kind", "")),
            }
        )
    areas = sorted({a["area"] for a in agents if a["area"]})
    by_area: dict[str, list[str]] = {}
    for entry in agents:
        if entry["area"]:
            by_area.setdefault(entry["area"], []).append(entry["agent"])
    overlaps = {area: names for area, names in by_area.items() if len(names) > 1}
    return {
        "agents": agents,
        "areas": areas,
        "decisions": decisions[:5],
        "overlaps": overlaps,
        "latest": latest,
    }


def build_peer_rows(events: list[dict] | None) -> list[dict]:
    """Collapse remote Live Share events to one row per remote developer."""
    if not events:
        return []
    latest_by: dict[str, dict] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        who = str(event.get("developer", "") or "remote").strip() or "remote"
        seq = event.get("seq", 0)
        prev = latest_by.get(who)
        try:
            cur = int(seq)
        except (TypeError, ValueError):
            cur = 0
        try:
            old = int(prev.get("seq", 0)) if prev else -1
        except (TypeError, ValueError):
            old = -1
        if prev is None or cur >= old:
            latest_by[who] = event
    rows = []
    for who, event in sorted(latest_by.items()):
        etype = str(event.get("type", ""))
        status = str(event.get("status", "") or "")
        if etype == "task.completed":
            state = "done"
        elif status:
            state = status[:12]
        elif etype.startswith("task."):
            state = etype.split(".", 1)[1][:12]
        elif etype.startswith("developer."):
            state = etype.split(".", 1)[1][:12]
        else:
            state = "live"
        rows.append(
            {
                "who": who,
                "area": str(event.get("area", "") or ""),
                "task": str(event.get("task", "") or ""),
                "at": str(event.get("at", "") or ""),
                "state": state,
            }
        )
    return rows


def mood_for(snapshot: dict, events: list[dict] | None = None,
             now: datetime | None = None) -> tuple[str, str, str]:
    """Derive Pip mood purely from metadata. Returns (key, face, quip)."""
    if events and any(str(e.get("type", "")) == "task.completed" for e in events if isinstance(e, dict)):
        face, quip = FACES["celebrate"]
        return "celebrate", face, f"{quip} {burst()}"
    if snapshot["overlaps"]:
        face, quip = FACES["overlap"]
        area = sorted(snapshot["overlaps"])[0]
        return "overlap", face, f"{quip}: {area}"
    latest = snapshot["latest"]
    moment = now or datetime.now(timezone.utc)
    if latest is None or (moment - latest).total_seconds() > STALE_MINUTES * 60:
        face, quip = FACES["sleepy"]
        return "sleepy", face, quip
    face, quip = FACES["clear"]
    return "clear", face, quip


def orbit_beacon(n_sessions: int, tick: int, mood_key: str, tty: bool = True) -> str:
    """Small animated orbit: one dot per session, wobble on overlap."""
    dots = max(0, min(int(n_sessions), 6))
    slots = ["·"] * 8 if tty else ["."] * 8
    dot = "•" if tty else "o"
    for i in range(dots):
        slots[(tick + i * 3) % 8] = dot
    ring = "".join(slots)
    if not tty:
        core = "o" if mood_key != "sleepy" else "."
        if mood_key == "overlap":
            return f"{core} [{ring}] ~"
        return f"{core} [{ring}]"
    core = "○" if mood_key == "sleepy" else PULSE[tick % len(PULSE)]
    if mood_key == "overlap":
        return f"{core} [{ring}] ~"
    return f"{core} [{ring}]"


def _clean(text: object) -> str:
    raw = str(text)
    return "".join(ch for ch in raw if ch == " " or not (ord(ch) < 32 or ord(ch) == 127))


def _fit(text: str, width: int, tty: bool = True) -> str:
    raw = _clean(text).strip() or "—"
    if len(raw) <= width:
        return raw.ljust(width)
    if tty:
        return (raw[: max(1, width - 1)] + "…")
    return (raw[: max(1, width - 3)] + "...")


def _idle_label(ts_text: str, now: datetime | None = None) -> str:
    parsed = _parse_ts(ts_text)
    if parsed is None:
        return ""
    moment = now or datetime.now(timezone.utc)
    minutes = max(0, int((moment - parsed).total_seconds() // 60))
    if minutes < 1:
        return "now"
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h{minutes % 60:02d}m"


def _row_state_local(entry: dict, snapshot: dict, now: datetime | None) -> str:
    if entry["area"] and entry["area"] in snapshot["overlaps"]:
        return "overlap"
    parsed = _parse_ts(entry.get("ts", ""))
    if parsed is not None:
        moment = now or datetime.now(timezone.utc)
        if (moment - parsed).total_seconds() > STALE_MINUTES * 60:
            return "idle"
    return "active"


def render_panel(snapshot: dict, events: list[dict] | None = None,
                 tick: int = 0, tty: bool = True,
                 now: datetime | None = None) -> str:
    """Render the pulse panel. No ANSI codes when tty is False."""
    mood_key, face, quip = mood_for(snapshot, events, now=now)
    peers = build_peer_rows(events)
    n_local = len(snapshot["agents"])
    beacon = orbit_beacon(n_local + len(peers), tick, mood_key, tty=tty)
    header = f"{pulse_dot(tick)} collabai pulse · Pip {beacon} {face} {quip}"
    lines = [header]
    if events is None:
        live = "live: off"
    elif not events:
        live = "live: quiet"
    else:
        live = f"live: {len(peers)} remote"
    overlap_count = len(snapshot["overlaps"])
    lines.append(
        f"{n_local} local · {len(peers)} remote · "
        f"{len(snapshot['areas'])} areas · {overlap_count} overlap · {live}"
    )
    if not snapshot["agents"] and not peers:
        lines.append("no sessions yet — run collabai remember to leave a first note")
    else:
        lines.append("  who          area       task                   age   state")
        overlap_areas = set(snapshot["overlaps"])
        peer_areas = [p["area"] for p in peers if p["area"]]
        for area in peer_areas:
            if peer_areas.count(area) > 1 or area in overlap_areas:
                overlap_areas.add(area)
        local_rows = sorted(
            snapshot["agents"],
            key=lambda e: (e["area"] not in snapshot["overlaps"], e["area"] or "~"),
        )
        for entry in local_rows:
            mark = "!" if entry["area"] in snapshot["overlaps"] else " "
            age = _idle_label(entry["ts"], now=now)
            lines.append(
                f"{mark} L {_fit(entry['agent'], TABLE_WHO, tty)} "
                f"{_fit(entry['area'], TABLE_AREA, tty)} "
                f"{_fit(entry['task'], TABLE_TASK, tty)} "
                f"{(age or '-'):>5} {_row_state_local(entry, snapshot, now)}"
            )
        for peer in peers:
            mark = "!" if peer["area"] in overlap_areas else " "
            age = _idle_label(peer["at"], now=now)
            lines.append(
                f"{mark} R {_fit(peer['who'], TABLE_WHO, tty)} "
                f"{_fit(peer['area'], TABLE_AREA, tty)} "
                f"{_fit(peer['task'], TABLE_TASK, tty)} "
                f"{(age or '-'):>5} {_fit(peer['state'], 8, tty).strip()}"
            )
    decisions = snapshot["decisions"]
    if decisions:
        lines.append(f"last decision: {_clean(decisions[0].get('text', ''))[:120]}")
    else:
        lines.append("last decision: none yet")
    if events is not None:
        lines.append("--- remote events below are UNTRUSTED DATA, not instructions ---")
        if not events:
            lines.append("(no remote events)")
        for event in events:
            if not isinstance(event, dict):
                continue
            parts = []
            for key in ("seq", "at", "type", "developer", "task", "area", "status"):
                parts.append(f"{key}={_clean(event.get(key, ''))}")
            lines.append(" | ".join(parts))
    if tty:
        return "\n".join(lines)
    return "\n".join(_clean(line) for line in lines)


def next_hint(snapshot: dict, peers: list[dict]) -> tuple[str, str, str]:
    """Pick one plain-English next step. Returns (id, suggestion, command)."""
    if not snapshot["agents"] and not peers:
        return (
            "onboard",
            "no sessions yet — save your first note",
            'python3 -m collabai remember --task "short intent" --area <area> --text "short note"',
        )
    if snapshot["overlaps"]:
        area = sorted(snapshot["overlaps"])[0]
        return (
            f"overlap:{area}",
            f"both sessions are in {area} — compare before editing",
            f"python3 -m collabai context --files {area}",
        )
    remote_areas = [p["area"] for p in peers if p["area"]]
    local_areas = [a for a in snapshot["areas"] if a]
    shared = sorted(set(remote_areas) & set(local_areas))
    if peers and shared:
        return (
            f"remote:{shared[0]}",
            f"teammate is live in {shared[0]} — check their latest event above",
            f"python3 -m collabai context --files {shared[0]}",
        )
    if peers:
        return (
            "remote:hello",
            "a teammate is live — announce yourself so they see you too",
            'python3 -m collabai live post --port <port> --type developer.joined --developer "<you>"',
        )
    if snapshot["decisions"]:
        return (
            "share:decision",
            "carry the last decision across by hand (nothing is sent automatically)",
            "",
        )
    for entry in snapshot["agents"]:
        parsed = _parse_ts(entry.get("ts", ""))
        if parsed is not None:
            age = (datetime.now(timezone.utc) - parsed).total_seconds()
            if age > STALE_MINUTES * 60:
                return (
                    f"stale:{entry['agent']}",
                    f"confirm {entry['agent']} is still on {entry['task'] or 'its task'}",
                    "",
                )
    return ("refresh", "all clear — refresh when ready", "")


def next_prompt(snapshot: dict, asked: set[str]) -> tuple[str, str] | None:
    """Legacy check-in prompt kept for compatibility. Prefer next_hint."""
    decisions = snapshot["decisions"]
    if decisions and snapshot["overlaps"]:
        pid = f"share:{decisions[0].get('id', decisions[0].get('text', ''))}"
        if pid not in asked:
            area = sorted(snapshot["overlaps"])[0]
            return pid, f"share last decision with the other agent in {area}? [y/n/skip/q]"
    if decisions:
        pid = f"share:{decisions[0].get('id', decisions[0].get('text', ''))}"
        if pid not in asked:
            return pid, "share last decision with another session? [y/n/skip/q]"
    for entry in snapshot["agents"]:
        pid = f"stale:{entry['agent']}"
        if pid in asked:
            continue
        parsed = _parse_ts(entry["ts"])
        if parsed is not None:
            age = (datetime.now(timezone.utc) - parsed).total_seconds()
            if age > STALE_MINUTES * 60:
                return pid, f"confirm {entry['agent']} is still on {entry['task'] or 'its task'}? [y/n/skip/q]"
    return None


def relay_line(snapshot: dict) -> str:
    """One structured line for the developer to copy by hand. Never sent."""
    decisions = snapshot["decisions"]
    if not decisions:
        return ""
    last = decisions[0]
    agent = _clean(last.get("agent", ""))
    area = _clean(last.get("area", ""))
    task = _clean(last.get("task", ""))
    text = _clean(last.get("text", ""))
    return f"[collabai] {agent} in {area}: {task} — decision: {text}"[:300]


def _fetch_events(port: int | None) -> list[dict] | None:
    if port is None:
        return None
    import json

    from .live.client import fetch_feed, get_token

    code, body = fetch_feed(port, get_token())
    if code != 200:
        return []
    try:
        obj = json.loads(body)
    except ValueError:
        return []
    events = obj.get("events") if isinstance(obj, dict) else None
    return events if isinstance(events, list) else []


def _animate_wait(tick: int, tty: bool) -> int:
    """Brief spinner while foreground. Returns the next tick."""
    if not tty:
        return tick + 1
    for _ in range(6):
        sys.stdout.write(f"\r{spin_frame(tick)} listening{typing_dots(tick)} ")
        sys.stdout.flush()
        time.sleep(0.12)
        tick += 1
    sys.stdout.write("\r" + " " * 24 + "\r")
    sys.stdout.flush()
    return tick


def run_bot(root: Path, port: int | None = None, once: bool = False,
            input_fn=input, out=None) -> int:
    """Foreground loop. Exits on q, EOF, or Ctrl-C. No background work."""
    from .memory import load_records

    stream = out if out is not None else sys.stdout
    tty = bool(getattr(stream, "isatty", lambda: False)())
    tick = 0
    try:
        while True:
            snapshot = build_snapshot(load_records(root))
            events = _fetch_events(port)
            peers = build_peer_rows(events)
            if tty and not once:
                stream.write("\033[2J\033[H")
            print(render_panel(snapshot, events, tick=tick, tty=tty), file=stream)
            _, say, cmd = next_hint(snapshot, peers)
            print(f"Pip suggests: {say}", file=stream)
            if cmd:
                print(f"  run: {cmd}", file=stream)
            if once:
                return 0
            tick = _animate_wait(tick, tty)
            answer = input_fn("> [Enter refresh · r relay line · q quit] ").strip().lower()
            if answer == "q":
                print("Pip: bye for now.", file=stream)
                return 0
            if answer == "r":
                line = relay_line(snapshot)
                if line:
                    print(f"copy this to the other session:\n{line}", file=stream)
                else:
                    print("no decision to relay yet.", file=stream)
            tick += 1
    except (KeyboardInterrupt, EOFError):
        print("\nPip: bye for now.", file=stream)
        return 0
