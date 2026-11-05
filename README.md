# collabai

Two humans. Two AI coding agents. One shared memory.

collabai is a local-first companion for pair programming across different AI coding agents. Each developer keeps their own agent — Claude Code, Codex, Muse, or anything else via the plain CLI. collabai carries only approved, structured knowledge between sessions: decisions, short notes, Git warnings, and questions an agent leaves for its developer.

Run `collabai` with no arguments to open the harness. No daemon. No cloud backend. Transcripts, diffs, prompts, and secrets are never captured.

## Install

Requires Python 3.11+. No sudo. Installs to `~/.local/bin`.

Python is required to run collabai — there is no separate app to install. Check first with `python3 --version`. If that command is not found or reports less than 3.11, install Python 3.11 or newer from [python.org](https://www.python.org/downloads/) (macOS/Windows) or your Linux distribution's package manager, then reopen the terminal and check again.

```bash
curl -fsSL https://github.com/wragorg/collabai/releases/latest/download/install.sh -o install.sh
# inspect install.sh, then:
sh install.sh
export PATH="$HOME/.local/bin:$PATH"
collabai --version
```

The installer downloads the release tarball and its `.sha256` over HTTPS, verifies the checksum before extracting, and writes a `~/.local/bin/collabai` shim. At the end it offers one optional step: a Meta API key for AI chat (see below). Blank skips it.

Update or remove an installed copy:

```bash
collabai --update              # latest release, checksum-verified
collabai --update --to 2.2.2   # a pinned version
collabai --uninstall           # asks separately: shim / versions / private state
```

## First pair session (5 minutes)

One-time setup per machine, in the same project:

```bash
collabai init
collabai adapter-claude-install   # Claude Code hook
collabai adapter-codex-install    # Codex AGENTS.md block
```

A decision crosses sessions without copy-paste:

```bash
# Dev A
collabai remember --task "Auth redesign" --area auth --files "auth/login.py" \
  --text "Use session cookies, not local tokens" --agent claude-code --decision
# Dev B
collabai context --files "auth/login.py"
```

Unrelated files print nothing (zero added tokens). Secret-shaped input is refused and nothing is stored.

Git awareness across machines: Dev A pushes as usual. Dev B runs `collabai git-fetch`, then `collabai git-check`, and is warned only when fetched changes touch known files or areas.

## The harness

`collabai` with no arguments opens a one-screen menu:

- **Collab Bot (1)** — who is working on what, overlaps first, one suggested next step.
- **Inbox (2)** — an agent that needs you leaves a short question (`collabai ask`); you answer it here without leaving the harness. With `collabai ask --wait`, the agent waits in the foreground for your answer (exit 2 on timeout); questions expire after 24 hours and are shown as untrusted data. collabai cannot push into a running agent session — the agent waits or comes back for the answer.
- **Remember (3)** — save a note. Type `@` to pick project files instead of typing paths; area and agent are filled in from last time.
- **Recall (4), Decide (5), Share (6)** — find past decisions, record an approved choice, print one relay line to paste to your pair. collabai never sends anything itself.
- **Launch (7)** — run `claude`, `codex`, or `muse` from inside the harness by terminal hand-over and return when it exits. The agent owns the terminal while it runs (notifications pause); questions that arrived meanwhile are flagged on return.
- **AI (8)** — Chat with Meta AI (below).
- **Git check (9), Doctor (10)** — fetched-change warnings and setup check.
- **Quit (11)** — exit. The menu is numbered in display order, 1 to 11, and a light Collab Bot animation runs at the top of the screen while it waits.

`collabai watch` is an opt-in, foreground-only watcher that prints new agent questions as they arrive. Ctrl-C stops it; nothing keeps running afterwards.

## Meta AI chat (menu 8)

Menu 8 is a free-form, multi-turn chat: type a prompt at `meta>`, get a reply, keep prompting (history carries across turns; `/clear` resets, `/save` saves the last reply through the normal Remember confirm, `/quit` returns). Only what you type at that prompt is sent to Meta; history is never written to disk and nothing is auto-saved.

It uses the Meta Model API (model `muse-spark-1.3`). You need a Model API key from the Meta dashboard — keys start with `LLM_`. Store one with `collabai --meta-key` (kept at `~/.config/collabai/meta.key`, `0600`, outside any repo; `COLLABAI_META_API_KEY` overrides, `--meta-key-remove` deletes).

Diagnose a key any time with:

```bash
collabai --meta-test   # one minimal call; prints "ready" on success
```

A bad key, wrong model, or rate limit each prints one readable line naming the problem — never a traceback. Everything else works exactly as without a key.

## Commands

| Command | Does |
|---|---|
| `collabai` | Open the harness |
| `init`, `status`, `doctor` | Set up and inspect local state |
| `remember`, `context`, `decide` | Save and recall approved notes and decisions |
| `bot` | Collab Bot panel |
| `ask [--wait]`, `inbox [--answer <id> [--wait]]`, `watch` | Agent questions: leave, list/answer, watch |
| `launch --agent <name>` | Run an agent here (terminal hand-over), return on exit |
| `git-fetch`, `git-check` | Explicit fetch, relevance warning |
| `--update`, `--uninstall` | Update or remove the installed copy |
| `--meta-key`, `--meta-key-remove`, `--meta-test` | Manage the optional Meta key; prove it with one call |
| `uninstall --yes` | Remove private state only |

## Privacy

- Memory and questions live in gitignored `.collabai/` (`0700`/`0600`). The Meta key lives outside the repo, also `0600`.
- Secrets are refused at write time. Nothing is transmitted by collabai itself except checksum-verified release downloads and, only with your key, metadata you approve for an AI extra.
- No network listener runs by default. Live Share is deferred (see Roadmap).
- Context your agent injects reaches your chosen model provider. That boundary is yours; preview exactly what would be sent with `collabai context --files "<paths>"`. See [the privacy and threat model](docs/privacy-threat-model.md).

## Troubleshooting

- `collabai: command not found` — add `~/.local/bin` to `PATH`.
- `not initialized` — run `collabai init` in the project root, or just run `collabai` and accept the first-run setup.
- Harness looks wrong in a pipe — it falls back to numbered picks without a TTY. Raw subcommands are the scripting surface.
- Running from a checkout: `export PYTHONPATH=/path/to/collabai` first.

## Roadmap

- **Live Share (deferred).** Temporary loopback sessions with SSH join. The loopback core and hardening are built; it returns only when the two-network transport story is designed and proven end to end. See [docs/ssh-tunnel.md](docs/ssh-tunnel.md).

Status: v2.2.2. Python 3.11+ stdlib only. Apache-2.0. See [CHANGELOG.md](CHANGELOG.md).

Known limits, by design: launch is terminal hand-over only; agent questions are answered by waiting (`--wait`) or on the agent's next read, never pushed into a running session; Meta AI chat sends only what you type at its prompt; Live Share is deferred (above).
