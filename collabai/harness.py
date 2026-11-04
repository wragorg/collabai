"""Retro mini-harness. Humans only; agents keep using the raw subcommands.

`collabai` with no arguments lands here. Every pick is a guided form over the
same library calls the CLI handlers use. Nothing is sent anywhere; Share only
prints a line for the human to copy. Stdlib only, foreground only.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

MENU: list[tuple[str, str, str, str]] = [
    ("1", "RIGHT NOW", "See who's doing what", "Collab Bot"),
    ("2", "DO SOMETHING", "Save a note or decision", "Remember"),
    ("3", "DO SOMETHING", "Find a past decision", "Recall"),
    ("4", "DO SOMETHING", "Record a choice we approved", "Decide"),
    ("5", "DO SOMETHING", "Send a decision to my pair", "Share"),
    ("6", "CHECK", "Did upstream change my files?", "Git check"),
    ("7", "CHECK", "Is my setup OK?", "Doctor"),
    ("8", "CHECK", "Leave", "Quit"),
]

LOGO = "C O L L A B A I"


def render_splash(version: str, tick: int = 0, color: bool = False) -> str:
    from .bot import orbit_beacon, paint

    beacon = orbit_beacon(3, tick, "clear", tty=True)
    title = f"   {LOGO}   ·   v{version}"
    lines = [
        "========================================",
        paint(title, "pip", color),
        f"   pair-programming companion   Collab Bot {beacon}",
        "========================================",
    ]
    return "\n".join(lines)


def render_menu(version: str, tick: int = 0, color: bool = False,
                suggest: str = "") -> str:
    from .bot import paint

    rows = [render_splash(version, tick, color)]
    group = ""
    for key, grp, label, cmd in MENU:
        if grp != group:
            group = grp
            rows.append(paint(f"  {grp}", "dim", color))
        rows.append(f"    {key}  {label}".ljust(38) + f"({cmd})")
    rows.append("  pick a number, Enter runs it, q quits")
    if suggest:
        rows.append(paint(f"  Collab Bot suggests: {suggest}", "pip", color))
    return "\n".join(rows)


def render_boot(tick: int) -> str:
    from .bot import boot_line

    return boot_line(tick, tty=True)


def render_idle(tick: int, color: bool = False) -> str:
    """One live prompt line: cyan beacon, dim prompt, typed text appended."""
    from .bot import orbit_beacon, paint

    beacon = orbit_beacon(3, tick, "clear", tty=True)
    return paint(f"Collab Bot {beacon}", "pip", color) + paint(" > ", "dim", color)


def _read_line_live(tick: int, color: bool) -> tuple[str | None, int]:
    """Read one line char-by-char, redrawing the beacon while idle.

    Returns (line, tick). Line is None when live mode is unavailable and the
    caller should fall back to input(). Restores the terminal on every exit.
    """
    import select

    try:
        import termios
        import tty as _tty
    except ImportError:
        return None, tick
    try:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
    except (OSError, ValueError):
        return None, tick
    buf: list[str] = []
    idle = 0
    try:
        _tty.setcbreak(fd)
        sys.stdout.write(render_idle(tick, color))
        sys.stdout.flush()
        while True:
            ready, _, _ = select.select([fd], [], [], 0.45)
            if not ready:
                idle += 1
                sys.stdout.write("\r\x1b[K" + render_idle(tick + idle, color) + "".join(buf))
                sys.stdout.flush()
                continue
            ch = os.read(fd, 1).decode(errors="ignore")
            if ch in ("\n", "\r"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                return "".join(buf).strip(), tick + idle
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch == "\x04" and not buf:
                raise EOFError
            if ch in ("\x7f", "\x08"):
                if buf:
                    buf.pop()
                    sys.stdout.write("\r\x1b[K" + render_idle(tick + idle, color) + "".join(buf))
                    sys.stdout.flush()
                continue
            if ch >= " ":
                buf.append(ch)
                sys.stdout.write(ch)
                sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return "".join(buf).strip(), tick + idle


def _ask(input_fn, label: str) -> str:
    return str(input_fn(label)).strip()


def _state_ready(root: Path) -> bool:
    return (root / ".collabai" / "config.json").exists()


def _do_init(root: Path) -> None:
    from .cli import DEFAULT_CONFIG, STATE_DIR_NAME

    state = root / STATE_DIR_NAME
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(state, 0o700)
    except OSError:
        print(f"warning: could not lock down {state}", file=sys.stderr)
    cfg = state / "config.json"
    cfg.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(cfg, 0o600)
    except OSError:
        print(f"warning: could not lock down {cfg}", file=sys.stderr)
    print(f"initialized collabai in {root} (private state in {STATE_DIR_NAME}/)")


def _remember_form(root: Path, input_fn) -> None:
    from .memory import save_record

    task = _ask(input_fn, "task (short intent): ")
    area = _ask(input_fn, "area (module, blank ok): ")
    files_raw = _ask(input_fn, "files (comma-separated, blank ok): ")
    text = _ask(input_fn, "note (max 500 chars): ")
    agent = _ask(input_fn, "agent (e.g. claude-code, codex): ") or "manual"
    decision = _ask(input_fn, "save as decision? [y/N]: ").lower() == "y"
    files = [s.strip() for s in files_raw.split(",") if s.strip()]
    try:
        rec = save_record(
            root,
            kind="decision" if decision else "ephemeral",
            agent=agent,
            task=task,
            area=area,
            files=files,
            text=text,
        )
    except ValueError as exc:
        print(str(exc))
        return
    print(f"saved {rec['kind']} {rec['id']}")


def _recall_form(root: Path, input_fn) -> None:
    from .memory import load_records, render_context

    raw = _ask(input_fn, "files to match (comma-separated): ")
    files = [s.strip() for s in raw.split(",") if s.strip()]
    out = render_context(load_records(root), files, max_chars=1000)
    print(out if out else "(nothing saved for those files yet)")


def _decide_form(root: Path, input_fn) -> None:
    from .memory import save_record

    question = _ask(input_fn, "the decision, in your words: ")
    raw = _ask(input_fn, "2-3 alternatives separated by | : ")
    options = [o.strip() for o in raw.split("|") if o.strip()][:3]
    if len(options) < 2:
        print("give 2-3 alternatives separated by |")
        return
    choice = _ask(input_fn, "your approved choice: ")
    area = _ask(input_fn, "area (blank ok): ")
    files_raw = _ask(input_fn, "files (comma-separated, blank ok): ")
    agent = _ask(input_fn, "agent (e.g. claude-code): ") or "manual"
    files = [s.strip() for s in files_raw.split(",") if s.strip()]
    text = f"Options: {'; '.join(options)}. Approved: {choice}"
    try:
        rec = save_record(root, kind="decision", agent=agent, task=question,
                          area=area, files=files, text=text)
    except ValueError as exc:
        print(str(exc))
        return
    print(f"saved decision {rec['id']}: {choice}")


def _share_form(root: Path) -> None:
    from .bot import build_snapshot, relay_line
    from .memory import load_records

    snapshot = build_snapshot(load_records(root))
    line = relay_line(snapshot)
    if line:
        print(f"copy this to the other developer:\n{line}")
    else:
        print("no decision to share yet — save one first (menu 4).")


def _git_check(root: Path) -> None:
    from .git_awareness import changed_since_upstream
    from .memory import load_records

    changed, note = changed_since_upstream(root)
    if note:
        print(note)
        return
    if not changed:
        print("no fetched changes")
        return
    known: set[str] = set()
    for rec in load_records(root):
        for f in rec.get("files", []):
            known.add(str(f).lower())
        if rec.get("area"):
            known.add(str(rec["area"]).lower())
    relevant = [f for f in changed
                if any(k and (k in f.lower() or f.lower() in k) for k in known)]
    if not relevant:
        print(f"{len(changed)} fetched file(s), none match local context")
        return
    print("relevant fetched changes (local assumptions may be stale):")
    for f in relevant[:20]:
        print(f"  {f}")


def _wizard(root: Path, input_fn) -> None:
    if _ask(input_fn, "Collab Bot: first time here — set up this project? [y/n] ").lower() != "y":
        print("ok — menu still works; run setup any time with: collabai init")
        return
    _do_init(root)
    pick = _ask(input_fn, "hook up which agent? [c]laude / c[x] codex / [s]kip: ").lower()
    if pick == "c":
        from .adapters import claude as _claude

        _claude.apply(root)
    elif pick == "x":
        from .adapters import codex as _codex

        _codex.apply(root)
    if _ask(input_fn, "save a first note now? [y/n] ").lower() == "y":
        _remember_form(root, input_fn)


def run_harness(root: Path, input_fn=input) -> int:
    """Menu loop. Exits on q, 8, EOF, or Ctrl-C. No background work."""
    import time as _time

    from . import __version__
    from .bot import build_snapshot, next_hint, run_bot, wants_anim, wants_color
    from .memory import load_records

    tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    color = wants_color(tty)
    try:
        if wants_anim(tty):
            from .bot import paint as _paint

            for frame in range(7):
                sys.stdout.write("\r" + _paint(render_boot(frame), "pip", color).ljust(60))
                sys.stdout.flush()
                _time.sleep(0.15)
            sys.stdout.write("\n")
            sys.stdout.flush()
        live = wants_anim(tty) and input_fn is input
        if not _state_ready(root):
            _wizard(root, input_fn)
        tick = 0
        while True:
            snapshot = build_snapshot(load_records(root))
            _, say, _cmd = next_hint(snapshot, [])
            print(render_menu(__version__, tick, color, suggest=say))
            if live:
                picked, tick = _read_line_live(tick, color)
                choice = picked if picked is not None else _ask(input_fn, "> ")
            else:
                choice = _ask(input_fn, "> ")
            if choice in ("q", "8"):
                print("Collab Bot: bye for now.")
                return 0
            if choice == "":
                tick += 1
                continue
            if choice == "1":
                run_bot(root, input_fn=input_fn)
                tick += 1
                continue
            elif choice == "2":
                _remember_form(root, input_fn)
            elif choice == "3":
                _recall_form(root, input_fn)
            elif choice == "4":
                _decide_form(root, input_fn)
            elif choice == "5":
                _share_form(root)
            elif choice == "6":
                _git_check(root)
            elif choice == "7":
                import argparse

                from .cli import cmd_doctor

                cmd_doctor(argparse.Namespace())
            else:
                print(f"no such pick: {choice}")
                tick += 1
                continue
            tick += 1
            _ask(input_fn, "press Enter to return: ")
    except (KeyboardInterrupt, EOFError):
        print("\nCollab Bot: bye for now.")
        return 0
