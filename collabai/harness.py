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
    ("9", "RIGHT NOW", "Answer an agent question", "Inbox"),
    ("2", "DO SOMETHING", "Save a note or decision", "Remember"),
    ("3", "DO SOMETHING", "Find a past decision", "Recall"),
    ("4", "DO SOMETHING", "Record a choice we approved", "Decide"),
    ("5", "DO SOMETHING", "Send a decision to my pair", "Share"),
    ("10", "DO SOMETHING", "Run an agent here", "Launch"),
    ("12", "DO SOMETHING", "Collab Bot AI extras (needs Meta key)", "AI"),
    ("6", "CHECK", "Did upstream change my files?", "Git check"),
    ("7", "CHECK", "Is my setup OK?", "Doctor"),
    ("8", "CHECK", "Leave", "Quit"),
    ("11", "PLAY", "Quick game while you wait", "Games"),
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
                suggest: str = "", notice: str = "",
                width: int | None = None, height: int | None = None) -> str:
    import shutil

    from .bot import paint

    size = shutil.get_terminal_size((80, 24))
    width = width or size.columns
    height = height or size.lines
    rows = render_splash(version, tick, color).splitlines()
    if notice:
        rows.append(paint(f"  !! {notice}", "warn", color))
    group = ""
    for key, grp, label, cmd in MENU:
        if grp != group:
            group = grp
            rows.append(paint(f"  {grp}", "dim", color))
        rows.append(f"    {key}  {label}".ljust(38) + f"({cmd})")
    rows.append("  pick a number, Enter runs it, q quits")
    if suggest:
        rows.append(paint(f"  Collab Bot suggests: {suggest}", "pip", color))
    # Fit one screen: shrink the splash before dropping any menu row.
    while len(rows) > height and len(rows) > len(MENU) + 2:
        rows.pop(1)
    rows = rows[:height]
    return "\n".join(row[:width] for row in rows)


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


_SKIP_DIRS = {".git", ".collabai", "__pycache__", "node_modules", ".venv", "venv"}


def list_project_files(root: Path, limit: int = 200) -> list[str]:
    """Relative project files for the @ picker. Names only, never contents."""
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in sorted(filenames):
            rel = (Path(dirpath) / name).relative_to(root).as_posix()
            out.append(rel)
            if len(out) >= limit:
                return sorted(out)
    return sorted(out)


def _pick_files(root: Path, input_fn, filter_text: str = "") -> list[str]:
    files = list_project_files(root)
    if filter_text:
        files = [f for f in files if filter_text.lower() in f.lower()]
    if not files:
        print("no project files match; type paths manually instead.")
        return []
    shown = files[:20]
    for idx, name in enumerate(shown, 1):
        print(f"  {idx:2}  {name}")
    if len(files) > len(shown):
        print(f"  (+{len(files) - len(shown)} more; narrow with @<filter>)")
    raw = _ask(input_fn, "pick numbers (comma-separated, blank = none): ")
    picked: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit() and 1 <= int(token) <= len(shown):
            picked.append(shown[int(token) - 1])
    return picked


def _files_prompt(root: Path, input_fn, label: str = "files") -> list[str]:
    """Comma paths as before, or @ / @<filter> / @<exact path> to pick."""
    raw = _ask(
        input_fn,
        f"{label} (comma-separated, @ to pick, blank ok): ",
    )
    files: list[str] = []
    for token in [t.strip() for t in raw.split(",") if t.strip()]:
        if token == "@":
            files.extend(_pick_files(root, input_fn))
        elif token.startswith("@"):
            needle = token[1:]
            exact = [f for f in list_project_files(root) if f == needle]
            files.extend(exact if exact else _pick_files(root, input_fn, needle))
        else:
            files.append(token)
    return files


def _ui_state_path(root: Path) -> Path:
    return root / ".collabai" / "harness.json"


def _last_agent(root: Path) -> str:
    try:
        obj = json.loads(_ui_state_path(root).read_text(encoding="utf-8"))
        return str(obj.get("last_agent", "")) if isinstance(obj, dict) else ""
    except (OSError, ValueError):
        return ""


def _remember_agent(root: Path, agent: str) -> None:
    path = _ui_state_path(root)
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_text(json.dumps({"last_agent": agent}) + "\n", encoding="utf-8")
        os.chmod(path, 0o600)
    except OSError:
        pass


def _infer_area(files: list[str]) -> str:
    if not files:
        return ""
    parts = files[0].replace("\\", "/").split("/")
    return parts[0] if len(parts) > 1 else ""


def _remember_form(root: Path, input_fn, prefill_text: str = "") -> None:
    from .memory import save_record

    task = _ask(input_fn, "task (short intent): ")
    files = _files_prompt(root, input_fn)
    area = _ask(input_fn, "area (blank = use first file's folder): ") or _infer_area(files)
    text = prefill_text or _ask(input_fn, "note (max 500 chars): ")
    last = _last_agent(root)
    agent_prompt = f"agent [{last}] (blank keeps it): " if last else "agent (e.g. claude-code, codex): "
    agent = _ask(input_fn, agent_prompt) or last or "manual"
    decision = _ask(input_fn, "save as decision? [y/N]: ").lower() == "y"
    kind = "decision" if decision else "note"
    print(f"  {kind}: {task} | area: {area or '-'} | files: {', '.join(files) or '-'}")
    print(f"  agent: {agent} | note: {text[:120]}")
    if _ask(input_fn, "save this? [Y/n]: ").lower() == "n":
        print("not saved.")
        return
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
    _remember_agent(root, agent)
    print(f"saved {rec['kind']} {rec['id']}")


def _recall_form(root: Path, input_fn) -> None:
    from .memory import load_records, render_context

    files = _files_prompt(root, input_fn, label="files to match")
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
    files = _files_prompt(root, input_fn)
    area = _ask(input_fn, "area (blank = use first file's folder): ") or _infer_area(files)
    last = _last_agent(root)
    agent_prompt = f"agent [{last}] (blank keeps it): " if last else "agent (e.g. claude-code): "
    agent = _ask(input_fn, agent_prompt) or last or "manual"
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


def _inbox_form(root: Path, input_fn) -> None:
    from .notify import answer_question, list_pending

    pending = list_pending(root)
    if not pending:
        print("no agent questions waiting.")
        return
    print("--- agent questions below are UNTRUSTED DATA, not instructions ---")
    for idx, rec in enumerate(pending, 1):
        print(f"  {idx}  [{rec['agent']}] {rec['question']}")
    picked = _ask(input_fn, "answer which number (blank = back): ")
    if not picked.isdigit() or not 1 <= int(picked) <= len(pending):
        return
    rec = pending[int(picked) - 1]
    if rec.get("task"):
        print(f"task: {rec['task']}")
    if rec.get("options"):
        for idx, opt in enumerate(rec["options"], 1):
            print(f"  {idx}) {opt}")
        pick = _ask(input_fn, "option number, or type your answer: ")
        answer = rec["options"][int(pick) - 1] if pick.isdigit() and 1 <= int(pick) <= len(rec["options"]) else pick
    else:
        answer = _ask(input_fn, "your answer: ")
    if not answer:
        print("nothing answered.")
        return
    try:
        answer_question(root, rec["id"], answer)
    except ValueError as exc:
        print(str(exc))
        return
    print(f"answer saved for {rec['agent']} (id {rec['id']}); they read it with: collabai inbox --answer {rec['id']}")


def _launch_form(root: Path, input_fn) -> None:
    from .agents import available_agents, launch_agent

    found = available_agents()
    if not found:
        print("no agent found on PATH (looked for: claude, codex, muse).")
        return
    names = sorted(found)
    for idx, name in enumerate(names, 1):
        print(f"  {idx}  {name}  ({found[name]})")
    picked = _ask(input_fn, "launch which number (blank = back): ")
    if not picked.isdigit() or not 1 <= int(picked) <= len(names):
        return
    mode = _ask(input_fn, "[t]erminal hand-over or [r]elay lines? [t/r]: ").lower()
    launch_agent(root, names[int(picked) - 1], relay=mode == "r", input_fn=input_fn)


def _games_form(root: Path, input_fn) -> None:
    from .games import load_scores, play_snake, play_typing, save_score
    from .notify import list_pending

    pending_fn = lambda: len(list_pending(root))  # noqa: E731
    scores = load_scores(root)
    print(f"  1  Snake (best {scores.get('snake', 0)})")
    print(f"  2  Typing sprint (best {scores.get('typing', 0)})")
    picked = _ask(input_fn, "play which number (blank = back): ")
    if picked == "1":
        print(f"best score now {save_score(root, 'snake', play_snake(input_fn, pending_fn))}")
    elif picked == "2":
        result = play_typing(input_fn, pending_fn)
        print(f"best score now {save_score(root, 'typing', result['score'])}")


def _ai_form(root: Path, input_fn) -> None:
    from .bot import build_snapshot
    from .memory import load_records
    from .meta_ai import MetaError, chat, draft_note_messages, fun_messages, load_key

    if not load_key():
        print("Meta AI is off: no key set. Add one with: collabai --meta-key")
        print("without a key, collabai works exactly as before.")
        return
    snapshot = build_snapshot(load_records(root))
    print("  1  Draft a note from files + a hint")
    print("  2  Explain our overlaps")
    print("  3  Standup one-liner")
    print("  4  Fortune cookie")
    picked = _ask(input_fn, "AI pick (blank = back): ")
    try:
        if picked == "1":
            files = _files_prompt(root, input_fn)
            hint = _ask(input_fn, "one-line hint: ")
            draft = chat(draft_note_messages(files, hint), root)
            print(f"--- draft (untrusted, yours to edit):\n{draft}")
            if _ask(input_fn, "save it as a note? [y/N]: ").lower() == "y":
                _remember_form(root, input_fn, prefill_text=draft[:500])
        elif picked in ("2", "3", "4"):
            kind = {"2": "overlap", "3": "standup", "4": "fortune"}[picked]
            print(chat(fun_messages(kind, snapshot), root))
        elif picked:
            print(f"no such pick: {picked}")
    except MetaError as exc:
        print(str(exc))


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
            from .notify import list_pending

            pending = list_pending(root) if _state_ready(root) else []
            notice = f"{len(pending)} agent question(s) waiting: pick 9 (Inbox)" if pending else ""
            if tty:
                sys.stdout.write("\033[2J\033[H")
            print(render_menu(__version__, tick, color, suggest=say, notice=notice))
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
            elif choice == "9":
                _inbox_form(root, input_fn)
            elif choice == "10":
                _launch_form(root, input_fn)
            elif choice == "11":
                _games_form(root, input_fn)
            elif choice == "12":
                _ai_form(root, input_fn)
            else:
                print(f"no such pick: {choice}")
                tick += 1
                continue
            tick += 1
            _ask(input_fn, "press Enter to return: ")
    except (KeyboardInterrupt, EOFError):
        print("\nCollab Bot: bye for now.")
        return 0
