# collabai — System overview for the next agent

Start here. For detail, read [the architecture guide](./Architecture.md).
For the two-developer story, read [the demo guide](./Demo.md).

## What this is

`collabai` (formerly PairBridge) is a local-first, privacy-first enhancer for
human-to-human pair programming across different AI coding agents. Developers
keep their own agent (Claude Code, Codex, later OpenCode) and gain cross-session
memory, decision reuse, Git awareness, and opt-in Live Share. It never runs its
own LLM, daemon, or cloud backend.

Modes: Local (works with no Git remote), Collaborative (same plus explicit
Git awareness on remotes), Live Share (temporary, opt-in, no remote needed).

## Current state — read before assuming

Verified manually by the owner (pasted terminal output, this session):

- CLI skeleton: `init`, `status`, `doctor`, `uninstall` (`install` is via installer, not a subcommand).
- Memory: JSONL store in `.collabai/memory/`, matching file returns one line, unrelated file returns nothing, secret input refused.
- Claude adapter: `SessionStart` hook merged into `.claude/settings.local.json` (private, uncommitted).
- Codex fallback: managed block appended to root `AGENTS.md`, second run reports already present.
- Cross-session recall demonstrated: Claude-saved decision read back via shared `context`.
- Real Claude Code session: `SessionStart` hook injected exactly one decision line, quoted verbatim by the model (owner-pasted output).
- Real Codex session: Codex ran the `AGENTS.md` recall command itself for `auth/login.py` and quoted the stored line; decision text was never hand-copied into the prompt (owner-pasted transcript).
- Negative session: empty project injected nothing; the model's only startup blocks were its own account/attribution context, explicitly "nothing else was shared" (owner-pasted reply).
- Live Share happy path: `task.started` posted, `seq` returned, no state files persisted.
- Git: `git-check` with no upstream and fetch/check with a remote both reported working.

Built but still needs an explicit pasted-output confirmation before calling it done:

- `decide` wrapper (question/options/choice) and its 2-option rejection.
- `install.sh` syntax (`sh -n`) and a real end-to-end install.

Verified hardening (owner-pasted outputs, this phase): Host-header rebinding
rejected (`403`), per-IP rate limit (`60`/min, then `429`), banned field
(`400`), oversize body (`413`), expired token (`401`), feed rendered as
bannered untrusted data with control characters stripped, broadened secret
refusal plus path validation, `.collabai/` untracked and gitignored,
`0700`/`0600` permissions restored, silent `chmod` failures now warn loudly.
Durable suite: `tests/test_security.py`, 21 stdlib `unittest` tests, all OK.

v1.0.1 is published (owner-proven: full suite, clean install with
checksum, harness save to Share relay to Recall across two machines).
Live Share stays PARKED; revival needs a two-network transport design.

v2.0.0 (hackathon branch `Enhancement/version_2`, built, not yet
owner-proofed — each item needs pasted terminal output before it is done):

- `--update` / `--uninstall` self-service (checksum fail-closed, rollback).
- Easy Remember: `@` file picker, inferred area, remembered agent, confirm.
- Harness fits one screen; beacon animates in the header, not the bottom.
- Agent question inbox (`ask`/`inbox`, menu 2) plus opt-in foreground
  `watch`; agents launchable from the harness (menu 7, relay is
  experimental and line-based).
- Optional Meta AI extras (menu 8): key at `~/.config/collabai/meta.key`
  (`0600`, outside any repo), default model `meta-spark-1.3`. The model
  id and endpoint are unverified until an owner-pasted smoke call passes.
- Docs rewritten for judges; README carries a beta note.

Still open: two-real-developer test and Git-check warning beat are not
yet proofed. Exclude agent-prompting files (`System.md`,
`Architecture.md`, `Demo.md`, `docs/`) from the release tarball.

## Module map

- `collabai/cli.py` — argparse commands only, stdlib only.
- `collabai/memory.py` — `save_record`, `load_records`, `render_context`.
- `collabai/adapters/claude.py` — hook preview/apply in `.claude/settings.local.json`.
- `collabai/adapters/codex.py` — `collabai:start`/`end` block in `AGENTS.md`.
- `collabai/live/server.py` — `State`, `make_token`, `valid_event`, `run_host`.
- `collabai/live/client.py` — `get_token`, `post_event`, `fetch_feed`.
- `collabai/git_awareness.py` — explicit fetch plus upstream relevance check.
- `collabai/harness.py` — no-args menu, `@` picker, inbox/launch/games/AI forms.
- `collabai/updater.py` — `--update` (verified download, rollback) and `--uninstall`.
- `collabai/notify.py` — `.collabai/inbox/` questions (24h) and foreground `watch`.
- `collabai/agents.py` — launch claude/codex/muse (hand-over or line relay).
- `collabai/meta_ai.py` — optional Meta extras; key outside any repo, metadata only.
- `install.sh` — `curl -fsSL` installer to `~/.local`, no sudo, optional Meta key at the end.
- `docs/` — SSH guide, privacy model, short architecture note, short demo sketch.

## Non-negotiables

Python 3.11+ stdlib only, no new dependencies without approval. State stays in
gitignored `.collabai/` (`0700`/`0600`). Live Share binds `127.0.0.1` only
with a 15-minute in-memory token, auth on every endpoint, no secrets, diffs,
transcripts, or prompts ever transmitted. Empty context costs zero tokens.
Never claim verification without owner-pasted results.

Working rules for this owner: ask before architectural decisions or
dependencies; never execute shell/Git/test commands yourself (suggest them,
owner runs them); work incrementally and get approval per increment.
