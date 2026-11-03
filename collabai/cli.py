"""collabai CLI skeleton (stdlib only, no third-party deps).

Commands: init, status, doctor, uninstall.
Live Share, memory, and adapters land in later increments.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__

STATE_DIR_NAME = ".collabai"
CONFIG_NAME = "config.json"

DEFAULT_CONFIG = {
    "version": 1,
    "live_share": {"enabled": False},
    "git": {"fetch_opt_in": False, "interval_seconds": 3600},
    "telemetry": {"enabled": False},
    "inference": {"extra_llm": False},
}


def _project_root(cwd: Path) -> Path:
    return cwd


def _state_dir(root: Path) -> Path:
    return root / STATE_DIR_NAME


def _read_config(root: Path) -> dict | None:
    cfg_path = _state_dir(root) / CONFIG_NAME
    if not cfg_path.exists():
        return None
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cmd_init(args: argparse.Namespace) -> int:
    root = _project_root(Path.cwd())
    state = _state_dir(root)
    try:
        state.mkdir(mode=0o700, exist_ok=True)
    except OSError as exc:
        print(f"collabai init failed: cannot create {state}: {exc}", file=sys.stderr)
        return 1
    cfg_path = state / CONFIG_NAME
    if cfg_path.exists() and not args.force:
        print(f"already initialized: {cfg_path} (use --force to reset config)")
        return 0
    try:
        os.chmod(state, 0o700)
    except OSError as exc:
        print(f"warning: could not lock down {state}: {exc}", file=sys.stderr)
    cfg_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(cfg_path, 0o600)
    except OSError as exc:
        print(f"warning: could not lock down {cfg_path}: {exc}", file=sys.stderr)
    print(f"initialized collabai in {root} (private state in {STATE_DIR_NAME}/)")
    print("private memory is local-only. live share is disabled by default.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    del args
    root = Path.cwd()
    cfg = _read_config(root)
    if cfg is None:
        print("not initialized (run: collabai init)")
        return 1
    print(f"collabai {__version__} initialized in {root}")
    print(f"live share: {'enabled' if cfg.get('live_share', {}).get('enabled') else 'disabled'}")
    print(f"git fetch opt-in: {cfg.get('git', {}).get('fetch_opt_in')}")
    print(f"telemetry: {'enabled' if cfg.get('telemetry', {}).get('enabled') else 'disabled'}")
    return 0


def _check(exe: str) -> str:
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if (Path(part) / exe).exists():
            return "found"
    return "not found"


def cmd_doctor(args: argparse.Namespace) -> int:
    del args
    print(f"collabai {__version__}")
    print(f"python: {sys.version.split()[0]} (need >= 3.11)")
    print(f"git: {_check('git')}")
    print(f"ssh: {_check('ssh')}")
    print(f"claude config: {'present' if Path.home().joinpath('.claude/settings.json').exists() else 'absent'}")
    codex_cfg = Path.home() / ".codex" / "config.toml"
    print(f"codex config: {'present' if codex_cfg.exists() else 'absent'}")
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    root = Path.cwd()
    state = _state_dir(root)
    if not state.exists():
        print("nothing to remove")
        return 0
    if not args.yes:
        print(f"would remove {state} (re-run with --yes to confirm)")
        return 0
    import shutil

    shutil.rmtree(state, ignore_errors=False)
    print("removed private collabai state. tracked files untouched.")
    return 0


def cmd_remember(args: argparse.Namespace) -> int:
    from pathlib import Path as _P

    from .memory import save_record

    root = _P.cwd()
    files = [s.strip() for s in (args.files or "").split(",") if s.strip()]
    try:
        rec = save_record(
            root,
            kind="decision" if args.decision else "ephemeral",
            agent=args.agent,
            task=args.task,
            area=args.area,
            files=files,
            text=args.text,
            shareable=args.shareable,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"saved {rec['kind']} {rec['id']}")
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    from pathlib import Path as _P

    from .memory import load_records, render_context

    root = _P.cwd()
    files = [s.strip() for s in (args.files or "").split(",") if s.strip()]
    out = render_context(load_records(root), files, max_chars=args.max_chars)
    if out:
        print(out)
    return 0


def cmd_claude_install(args: argparse.Namespace) -> int:
    from pathlib import Path as _P

    from .adapters import claude as _claude

    root = _P.cwd()
    if args.dry_run:
        print(_claude.preview(root))
        return 0
    return _claude.apply(root)


def cmd_codex_install(args: argparse.Namespace) -> int:
    from pathlib import Path as _P

    from .adapters import codex as _codex

    root = _P.cwd()
    if args.dry_run:
        print(_codex.preview(root))
        return 0
    return _codex.apply(root)


def cmd_live_host(args: argparse.Namespace) -> int:
    from .live.server import run_host

    if args.port != 0 and not 1024 <= args.port <= 65535:
        print("port must be 0 or 1024-65535", file=sys.stderr)
        return 1
    return run_host(port=args.port)


def cmd_live_post(args: argparse.Namespace) -> int:
    from .live.client import get_token, post_event

    event = {
        "type": args.etype,
        "developer": args.developer,
        "task": args.task,
        "area": args.area,
        "status": args.status,
    }
    code, body = post_event(args.port, get_token(), event)
    print(body)
    return 0 if code == 200 else 1


def cmd_live_feed(args: argparse.Namespace) -> int:
    from .live.client import fetch_feed, get_token

    code, body = fetch_feed(args.port, get_token(), since=args.since)
    from .live.client import render_feed

    print(render_feed(body))
    return 0 if code == 200 else 1


def cmd_git_fetch(args: argparse.Namespace) -> int:
    from pathlib import Path as _P

    from .git_awareness import do_fetch

    del args
    code, msg = do_fetch(_P.cwd())
    print(msg)
    return code


def cmd_git_check(args: argparse.Namespace) -> int:
    from pathlib import Path as _P

    from .git_awareness import changed_since_upstream
    from .memory import load_records

    del args
    root = _P.cwd()
    changed, note = changed_since_upstream(root)
    if note:
        print(note)
        return 0
    if not changed:
        print("no fetched changes")
        return 0
    known: set[str] = set()
    for rec in load_records(root):
        for f in rec.get("files", []):
            known.add(str(f).lower())
        if rec.get("area"):
            known.add(str(rec["area"]).lower())
    relevant = [f for f in changed if any(k and (k in f.lower() or f.lower() in k) for k in known)]
    if not relevant:
        print(f"{len(changed)} fetched file(s), none match local context")
        return 0
    print("relevant fetched changes (local assumptions may be stale):")
    for f in relevant[:20]:
        print(f"  {f}")
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    from pathlib import Path as _P

    from .memory import save_record

    options = [o.strip() for o in args.options.split("|") if o.strip()][:3]
    if len(options) < 2:
        print("give 2-3 alternatives separated by |", file=sys.stderr)
        return 1
    text = f"Options: {'; '.join(options)}. Approved: {args.choice}"
    files = [s.strip() for s in (args.files or "").split(",") if s.strip()]
    try:
        rec = save_record(
            _P.cwd(),
            kind="decision",
            agent=args.agent,
            task=args.question,
            area=args.area,
            files=files,
            text=text,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"saved decision {rec['id']}: {args.choice}")
    return 0


def cmd_bot(args: argparse.Namespace) -> int:
    from pathlib import Path as _P

    from .bot import run_bot

    return run_bot(_P.cwd(), port=args.port, once=args.once)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="collabai", description="collaborative intelligence, local-first")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("init", help="initialize project-local private state")
    pi.add_argument("--force", action="store_true", help="reset config to defaults")
    pi.set_defaults(func=cmd_init)
    ps = sub.add_parser("status", help="show local state")
    ps.set_defaults(func=cmd_status)
    pd = sub.add_parser("doctor", help="check environment without changing anything")
    pd.set_defaults(func=cmd_doctor)
    pu = sub.add_parser("uninstall", help="remove private local state only")
    pu.add_argument("--yes", action="store_true", help="confirm removal")
    pu.set_defaults(func=cmd_uninstall)
    pr = sub.add_parser("remember", help="save a short approved note (never a transcript)")
    pr.add_argument("--task", required=True, help="short task intent you approve")
    pr.add_argument("--area", default="", help="module or area name")
    pr.add_argument("--files", default="", help="comma-separated paths")
    pr.add_argument("--text", default="", help="short summary, max 500 chars")
    pr.add_argument("--agent", default="manual", help="agent identifier")
    pr.add_argument("--decision", action="store_true", help="store as persistent decision")
    pr.add_argument("--shareable", action="store_true", help="mark shareable (default private)")
    pr.set_defaults(func=cmd_remember)
    pc = sub.add_parser("context", help="print filtered context (empty when irrelevant)")
    pc.add_argument("--files", default="", help="comma-separated paths to match")
    pc.add_argument("--max-chars", type=int, default=1000, help="cap output (~250 tokens)")
    pc.set_defaults(func=cmd_context)
    pa = sub.add_parser("adapter-claude-install", help="preview or install Claude hook")
    pa.add_argument("--dry-run", action="store_true", help="show diff without writing")
    pa.set_defaults(func=cmd_claude_install)
    px = sub.add_parser("adapter-codex-install", help="preview or install Codex AGENTS.md block")
    px.add_argument("--dry-run", action="store_true", help="show diff without writing")
    px.set_defaults(func=cmd_codex_install)
    pl = sub.add_parser("live", help="temporary opt-in live collaboration")
    plsub = pl.add_subparsers(dest="live_cmd", required=True)
    ph = plsub.add_parser("host", help="start loopback-only host (prints token once)")
    ph.add_argument("--port", type=int, default=0, help="loopback port (0 = ephemeral)")
    ph.set_defaults(func=cmd_live_host)
    pp = plsub.add_parser("post", help="post one approved event (token via env or prompt)")
    pp.add_argument("--port", type=int, required=True)
    pp.add_argument("--type", dest="etype", required=True)
    pp.add_argument("--developer", default="")
    pp.add_argument("--task", default="")
    pp.add_argument("--area", default="")
    pp.add_argument("--status", default="")
    pp.set_defaults(func=cmd_live_post)
    pf = plsub.add_parser("feed", help="fetch approved events (token via env or prompt)")
    pf.add_argument("--port", type=int, required=True)
    pf.add_argument("--since", type=int, default=0)
    pf.set_defaults(func=cmd_live_feed)
    pg = sub.add_parser("git-fetch", help="explicit git fetch only (never merges)")
    pg.set_defaults(func=cmd_git_fetch)
    pk = sub.add_parser("git-check", help="warn about fetched changes to relevant files")
    pk.set_defaults(func=cmd_git_check)
    pd2 = sub.add_parser("decide", help="record an approved decision with alternatives")
    pd2.add_argument("--question", required=True, help="the decision, in your words")
    pd2.add_argument("--options", required=True, help="2-3 alternatives, separated by |")
    pd2.add_argument("--choice", required=True, help="your approved choice")
    pd2.add_argument("--area", default="")
    pd2.add_argument("--files", default="")
    pd2.add_argument("--agent", default="manual")
    pd2.set_defaults(func=cmd_decide)
    pbot = sub.add_parser("bot", help="foreground companion panel (Pip, metadata only)")
    pbot.add_argument("--port", type=int, default=None, help="live host port (optional)")
    pbot.add_argument("--once", action="store_true", help="print panel once and exit")
    pbot.set_defaults(func=cmd_bot)
    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))
