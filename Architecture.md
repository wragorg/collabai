# collabai — Architecture

Detailed design for the next implementer. Read [the system overview](./System.md)
first. Every choice here favours the 4-day MVP: simplicity, privacy, and zero
new dependencies over generality.

## Principles and invariants

1. Python 3.11+ standard library only (`argparse`, `json`, `http.server`, `secrets`, `subprocess`). Introducing a dependency needs owner approval.
2. No permanent daemon, backend, event bus, or extra inference. Existing agents do the reasoning.
3. Privacy by construction, not policy text: nothing is captured unless the developer explicitly runs `remember`/`decide`/`live post`; secrets are refused at write time; private state is `0700`/`0600` and gitignored.
4. Token frugality: `collabai context` prints at most ~1,000 chars (~250 tokens) and prints nothing when irrelevant. No transcript injection.
5. Graceful failure: if collabai is absent or Live Share dies, agents work normally. Hooks and adapters must never block agent startup on error.

## Components

### CLI (`collabai/cli.py`)

Single argparse entry (`collabai.__main__:main`). Handlers are thin wrappers:
`cmd_init`, `cmd_status`, `cmd_doctor`, `cmd_uninstall`, `cmd_remember`,
`cmd_context`, `cmd_decide`, `cmd_claude_install`, `cmd_codex_install`,
`cmd_live_host`, `cmd_live_post`, `cmd_live_feed`, `cmd_git_fetch`,
`cmd_git_check`. Defaults in `DEFAULT_CONFIG`: live disabled, fetch opt-in
false, telemetry off, extra LLM off. `uninstall` removes `.collabai/` only,
after `--yes`. Keep handlers non-interactive except secret prompts.

### Memory (`collabai/memory.py`)

Files: `.collabai/memory/ephemeral.jsonl` and `decisions.jsonl`. One JSON
object per line with `id`, `ts`, `agent`, `task` (≤200), `area`, `files`
(≤20), `kind`, `text` (≤500), `shareable` (default false), `expires_at`.
Ephemeral expiry is 7 days; decisions do not expire. Appends use `fcntl.flock`
when available. `_ensure_file` creates `0700` dirs and `0600` files and
warns on stderr if `chmod` fails instead of passing silently. Secret
patterns (private-key header, AWS/GitHub/provider tokens, JWTs, bearer
and `key=`/`password=` style assignments) are checked across task, text,
area, files, and agent together and raise `refused:`, storing nothing.
File paths are validated: absolute paths, `..` traversal, and secret
filenames (`.env`, key and cert files) refuse the whole record.
Never rely on file-extension filtering alone.
Dedup is by recency order on read (`load_records` sorts newest first).

### Context injection (`render_context`)

Load all valid records. If `--files` is given, keep only records whose file
or area overlaps (case-insensitive substring either way); otherwise keep
decisions only, at most five, each rendered as `- [area] task: text`.
Truncating at `max_chars` (default 1000) guarantees the budget. Empty output
is the correct result for unrelated work — do not add filler text.

### Adapters

Claude Code (`collabai/adapters/claude.py`): merge `{"hooks":{"SessionStart":
[{"matcher":"*","hooks":[{"type":"command","command":"python3 -m collabai context"}]}]}}`
into `.claude/settings.local.json` only. `preview` shows current plus
would-add without writing; `apply` skips if the command already exists and
never touches shared `settings.json`. Hook stdout becomes session context;
empty stdout costs zero tokens and never blocks startup.

Codex (`collabai/adapters/codex.py`): root `AGENTS.md` is the guaranteed
instruction surface. `preview`/`apply` ensure one block between
`<!-- collabai:start -->` and `<!-- collabai:end -->`, appending to existing
content and refusing duplicates. The block teaches recall/save commands and
privacy rules. No scraping of Codex internals.

OpenCode has no dedicated adapter in the MVP (deferred per the PRD). It works
today via the same generic `context`/`remember` CLI run by hand or from any
hook OpenCode exposes later. Do not claim tighter integration until a PoC
proves the mechanism.

### Live Share (`collabai/live/`)

`State` holds a `secrets`-generated token (15-minute expiry), sequence
counter, and a bounded in-memory queue (max 100). `valid_event` accepts only
`developer.joined/left`, `task.started/updated/completed`, `module.activity`,
`decision.shared`, caps string fields at 200 chars, and rejects banned keys
(`code`, `diff`, `transcript`, `prompt`, `secret`, `token`). `make_handler`
serves `127.0.0.1` only via `ThreadingHTTPServer`; every endpoint requires
`Authorization: Bearer` compared with `hmac.compare_digest`; bodies over
4 KB get `413`; logging is silenced so tokens never reach logs. `run_host`
prints port and token to the host terminal once and revokes on Ctrl-C.
Requests first pass a Host-header allowlist (`127.0.0.1`/`localhost` only,
else `403`, blocking DNS rebinding) and a per-IP token bucket (60 requests
per 60 seconds, then `429`), checked before auth. `render_feed` displays
remote events as bannered untrusted data with control characters stripped;
they are never instructions.

Client (`get_token`, `post_event`, `fetch_feed`) reads the token only from
`COLLABAI_TOKEN` or a hidden prompt — never a `--token` flag (it would show
in `ps`). Remote access is the joiner’s own `ssh -L` forward to the host
loopback port. See the SSH guide in `docs/`. File paths are private until
the developer explicitly posts them.

### Git awareness (`collabai/git_awareness.py`)

`do_fetch` runs `git fetch --prune` (explicit command only; no polling in
the MVP, no `.git` writes beyond refs). `changed_since_upstream` resolves
`@{u}` and diffs `HEAD...@{u}`. `cmd_git_check` intersects changed paths
with memory files/areas and warns only on overlap, marking assumptions
stale. It never commits, merges, pushes, resets, or rebases, and degrades
to a plain message when there is no repo or upstream.

### Decisions (`cmd_decide`)

Thin wrapper: `--question`, `--options "A|B"` (2–3, split on `|`), `--choice`
(the developer’s approved pick). Stored as a decision record whose text is
`Options: ... Approved: ...`. Agents surface alternatives; only the explicit
choice is persisted.

### Bot and harness (built)

Collab Bot (`collabai/bot.py`) and the no-args harness
(`collabai/harness.py`) stay inside the invariants: foreground, on-demand,
interactive only while the command runs. They track structured metadata
only (sessions, agents, tasks, decisions, live events); never
transcripts, diffs, prompts, or secrets. The harness renders one screen,
animates its beacon in the header line, and picks project files with `@`
(file names only, contents never read).

### v2 additions (hackathon branch, owner-approved architecture change)

- `collabai/updater.py`: `--update` downloads a release tarball and its
  `.sha256` over HTTPS only, verifies fail-closed, and swaps the version
  directory under `~/.local/share/` (old shim/dir restored on failure).
  `--uninstall` asks separately about shim, version dirs, and state.
- `collabai/notify.py`: agent questions in `.collabai/inbox/` — short,
  secret-scanned, `0600`, 24-hour expiry, answered in the harness (menu 2).
  `collabai watch` is an opt-in foreground poller; it is the one piece
  that watches while the harness is not on screen, and stopping it
  leaves nothing running. No silent daemon is ever installed.
- `collabai/agents.py`: menu 7 launches `claude`/`codex`/`muse` in the
  harness (terminal hand-over, or an experimental line relay). The
  developer types every answer and command approval; nothing auto-runs.
- `collabai/meta_ai.py`: optional Meta AI extras behind a key stored at
  `~/.config/collabai/meta.key` (`0600`, outside any repo; env override).
  Default model `meta-spark-1.3`, named on every use. Metadata-only
  inputs, output never auto-saved. No key: identical v1 behaviour.

### Installer (`install.sh`)

Implemented `curl -fsSL` flow: enforce `python3` ≥ 3.11, download the
versioned release tarball (`wragorg/collabai`, `v<v>`) over HTTPS only,
verify the detached `.sha256` before extraction (fail closed), extract
under `~/.local/share/collabai-<v>`, verify `collabai/__main__.py` layout,
write a `~/.local/bin/collabai` shim, no sudo. Always instruct users to
download-then-inspect rather than blind-piping. Clean install of v1.0.1
was owner-proven; the v2.0.0 clean install and self-update still need an
owner-pasted proof against a published release. At the end of install,
the script offers `collabai --meta-key` (hidden prompt, blank skips;
model `meta-spark-1.3`).

## Repo shape and extension points

Keep `collabai/` (code), `docs/` (guides), `demo/` (synthetic project, to be
added), and `tests/` (focused owner-run suite, stdlib `unittest`) separate. A new agent
reuses the adapter contract: `install` (diff + approval), `on_session_start`
(filtered string or empty), `on_session_end` (structured fields only),
`uninstall`. A new Live event type needs a schema entry plus a privacy review.

## Verification habit

This project verifies manually: the implementing agent writes exact terminal
steps; the owner runs them and pastes output; only then is behaviour done.
Re-run history: skeleton, memory, both adapters, recall, live happy path,
both Git cases, `decide`, and the v1.0.1 clean install passed (owner-pasted).
v2 additions (updater, `@` picker, inbox/watch, launch, Meta extras, games)
are covered by unit tests and still need owner-pasted terminal proof.
Before tagging: secret-scan the repo, check `.collabai/` permissions,
fuzz `/events`, confirm token expiry, and clean-uninstall in a scratch dir.
