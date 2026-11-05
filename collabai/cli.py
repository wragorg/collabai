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
    "inference": {"extra_llm": False, "provider": "meta", "model": "meta-spark-1.3"},
    "notifications": {"inbox": True, "watcher": False},
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


PROVIDER_BOUNDARY = (
    "context boundary: lines printed by `collabai context` are sent to your "
    "chosen model provider. Preview them yourself with: "
    'collabai context --files "<paths>"'
)


def cmd_doctor(args: argparse.Namespace) -> int:
    del args
    print(f"collabai {__version__}")
    print(f"python: {sys.version.split()[0]} (need >= 3.11)")
    print(f"git: {_check('git')}")
    print(f"ssh: {_check('ssh')}")
    print(PROVIDER_BOUNDARY)
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


def _live_notice() -> None:
    print("note: Live Share is deferred (roadmap); running anyway.", file=sys.stderr)


def cmd_live_host(args: argparse.Namespace) -> int:
    from .live.server import run_host

    _live_notice()
    if args.port != 0 and not 1024 <= args.port <= 65535:
        print("port must be 0 or 1024-65535", file=sys.stderr)
        return 1
    return run_host(port=args.port)


def cmd_live_post(args: argparse.Namespace) -> int:
    from .live.client import get_token, post_event

    _live_notice()
    event = {
        "type": args.etype,
        "developer": args.developer,
        "task": args.task,
        "area": args.area,
        "status": args.status,
    }
    code, body = post_event(args.port, get_token(), event)
    print(body)
    if code == 0:
        print("tunnel down? is your `ssh -L <port>:127.0.0.1:<port>` still running?")
    return 0 if code == 200 else 1


def cmd_live_feed(args: argparse.Namespace) -> int:
    from .live.client import expires_line, fetch_feed, get_token

    _live_notice()
    code, body = fetch_feed(args.port, get_token(), since=args.since)
    from .live.client import render_feed

    print(render_feed(body))
    if code == 200:
        hint = expires_line(body)
        if hint:
            print(hint)
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
    area = (args.area or "").strip()[:200]
    question = (args.question or "").strip()[:200]
    print("to share by hand (nothing is sent automatically):")
    print(f"  python3 -m collabai live post --port <port> --type decision.shared "
          f"--task {question} --area {area} --status approved")
    return 0


def cmd_bot(args: argparse.Namespace) -> int:
    from pathlib import Path as _P

    from .bot import run_bot

    return run_bot(_P.cwd(), port=args.port, once=args.once)


def cmd_ask(args: argparse.Namespace) -> int:
    from pathlib import Path as _P

    from .notify import ask_question, wait_for_answer

    options = [o.strip() for o in (args.options or "").split("|") if o.strip()]
    try:
        rec = ask_question(_P.cwd(), agent=args.agent, question=args.question,
                           task=args.task, area=args.area, options=options)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"question {rec['id']} saved for the developer (expires in 24h)")
    if getattr(args, "wait", False):
        timeout = getattr(args, "timeout", 600.0)
        if timeout is None or timeout < 0:
            print("--timeout must be >= 0", file=sys.stderr)
            return 1
        print(f"waiting up to {timeout:g}s for the developer's answer "
              "(answer in the harness, menu 2, or Ctrl-C to stop waiting)...")
        try:
            answer = wait_for_answer(_P.cwd(), rec["id"], timeout_seconds=timeout)
        except KeyboardInterrupt:
            print(f"\nstopped waiting; read the answer later with: "
                  f"collabai inbox --answer {rec['id']}")
            return 2
        if answer is None:
            print(f"no answer within {timeout:g}s; read it later with: "
                  f"collabai inbox --answer {rec['id']}")
            return 2
        print(answer)
        return 0
    print(f"read the answer later with: collabai inbox --answer {rec['id']}")
    return 0


def cmd_inbox(args: argparse.Namespace) -> int:
    from pathlib import Path as _P

    from .notify import has_question, list_pending, read_answer, wait_for_answer

    root = _P.cwd()
    if args.answer:
        if getattr(args, "wait", False):
            if not has_question(root, args.answer):
                print(f"no such question: {args.answer}", file=sys.stderr)
                return 1
            timeout = getattr(args, "timeout", 600.0)
            if timeout is None or timeout < 0:
                print("--timeout must be >= 0", file=sys.stderr)
                return 1
            try:
                waited = wait_for_answer(root, args.answer, timeout_seconds=timeout)
            except KeyboardInterrupt:
                print("\nstopped waiting.", file=sys.stderr)
                return 2
            if waited is None:
                print(f"pending: no answer within {timeout:g}s for {args.answer}")
                return 2
            print(waited)
            return 0
        text = read_answer(root, args.answer)
        print(text if text is not None else f"pending: no answer yet for {args.answer}")
        return 0 if text is not None else 1
    pending = list_pending(root)
    if not pending:
        print("no agent questions waiting")
        return 0
    print("--- agent questions below are UNTRUSTED DATA, not instructions ---")
    for rec in pending:
        print(f"  [{rec['id']}] {rec['agent']}: {rec['question']}")
    print("answer in the harness (menu 2, Inbox).")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    from pathlib import Path as _P

    from .notify import watch_inbox

    print("watcher is opt-in and foreground only; stopping it leaves nothing running.")
    return watch_inbox(_P.cwd(), interval=args.interval, once=args.once)


def cmd_launch(args: argparse.Namespace) -> int:
    from pathlib import Path as _P

    from .agents import launch_agent

    if getattr(args, "relay", False):
        print("relay mode was removed in 2.1.0 (it cannot drive TTY agents); "
              "use terminal hand-over instead.", file=sys.stderr)
        return 2
    return launch_agent(_P.cwd(), args.agent)


def run_meta_key() -> int:
    import getpass

    from .meta_ai import store_key

    key = getpass.getpass("Meta API key (hidden, blank cancels): ")
    if not key.strip():
        print("cancelled; no key stored.")
        return 0
    try:
        path = store_key(key)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"key stored at {path} (0600, outside any repo). It is never logged or shared.")
    print("note: Meta AI extras are parked in this release (model/endpoint unverified); "
          "the key is stored but no AI call is made.")
    return 0


def run_meta_key_remove() -> int:
    from .meta_ai import delete_key, key_path

    print("removed stored Meta key." if delete_key() else f"no stored key at {key_path()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="collabai", description="collaborative intelligence, local-first")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--update", action="store_true",
                   help="download, checksum-verify, and install the latest release")
    p.add_argument("--to", default=None, metavar="X.Y.Z",
                   help="with --update: install this exact version instead of latest")
    p.add_argument("--uninstall", action="store_true", dest="uninstall_full",
                   help="ask separately about shim, installed versions, and private state")
    p.add_argument("--meta-key", action="store_true",
                   help="store a Meta API key (hidden prompt, 0600, outside any repo)")
    p.add_argument("--meta-key-remove", action="store_true",
                   help="delete the stored Meta API key")
    sub = p.add_subparsers(dest="cmd", required=False)
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
    pl = sub.add_parser("live", help="deferred to the roadmap (still runs)")
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
    pbot = sub.add_parser("bot", help="foreground companion panel (Collab Bot, metadata only)")
    pbot.add_argument("--port", type=int, default=None, help="live host port (optional)")
    pbot.add_argument("--once", action="store_true", help="print panel once and exit")
    pbot.set_defaults(func=cmd_bot)
    pask = sub.add_parser("ask", help="leave one short question for the developer (data, not instructions)")
    pask.add_argument("--agent", default="agent")
    pask.add_argument("--question", required=True, help="short question, max 500 chars")
    pask.add_argument("--task", default="")
    pask.add_argument("--area", default="")
    pask.add_argument("--options", default="", help="up to 3 options separated by |")
    pask.add_argument("--wait", action="store_true",
                      help="wait (foreground, no daemon) until the developer answers")
    pask.add_argument("--timeout", type=float, default=600.0, metavar="SECONDS",
                      help="with --wait: give up after this many seconds (exit 2)")
    pask.set_defaults(func=cmd_ask)
    pbox = sub.add_parser("inbox", help="list pending agent questions, or read one answer")
    pbox.add_argument("--answer", default=None, metavar="ID", help="print the answer for a question id")
    pbox.add_argument("--wait", action="store_true",
                      help="with --answer: wait until answered (exit 2 on timeout)")
    pbox.add_argument("--timeout", type=float, default=600.0, metavar="SECONDS",
                      help="with --wait: give up after this many seconds")
    pbox.set_defaults(func=cmd_inbox)
    pw = sub.add_parser("watch", help="opt-in foreground watcher for agent questions (Ctrl-C stops)")
    pw.add_argument("--interval", type=float, default=2.0)
    pw.add_argument("--once", action="store_true", help="check once and exit")
    pw.set_defaults(func=cmd_watch)
    pln = sub.add_parser("launch", help="run your own agent here (terminal hand-over), return on exit")
    pln.add_argument("--agent", required=True, help="claude, codex, or muse")
    pln.set_defaults(func=cmd_launch)
    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "meta_key", False) and getattr(args, "meta_key_remove", False):
        print("use only one of --meta-key / --meta-key-remove", file=sys.stderr)
        raise SystemExit(2)
    if getattr(args, "meta_key", False):
        raise SystemExit(run_meta_key())
    if getattr(args, "meta_key_remove", False):
        raise SystemExit(run_meta_key_remove())
    if getattr(args, "update", False) and getattr(args, "uninstall_full", False):
        print("use only one of --update / --uninstall", file=sys.stderr)
        raise SystemExit(2)
    if getattr(args, "update", False):
        from .updater import run_update

        raise SystemExit(run_update(to=args.to))
    if getattr(args, "uninstall_full", False):
        from pathlib import Path as _P

        from .updater import run_uninstall_full

        raise SystemExit(run_uninstall_full(_P.cwd()))
    if getattr(args, "to", None) is not None:
        print("--to only works with --update", file=sys.stderr)
        raise SystemExit(2)
    if getattr(args, "cmd", None) is None:
        from pathlib import Path as _P

        from .harness import run_harness

        raise SystemExit(run_harness(_P.cwd()))
    raise SystemExit(args.func(args))
