# collabai

Two humans. Two AI coding agents. One shared memory.

collabai is a local-first companion for human-to-human pair programming across different AI coding agents. You keep your own agent — Claude Code, Codex, or anything else via the plain CLI. collabai carries the approved, structured knowledge between you: decisions, context, and Git awareness. Run `collabai` with no arguments and a retro mini-harness walks you through everything. No extra LLM. No daemon. No cloud backend. No transcripts, diffs, or prompts are ever captured.

## Why download it

You and your pair each work in your own agent session, possibly on different machines. Without collabai, every decision has to be re-explained, re-pasted, and re-discovered in each session. With collabai:

- Record a decision once (`remember`, `decide`). Your partner recalls it from their own agent with one command.
- See at a glance what everyone is working on (`bot`). Collab Bot, the terminal companion, shows each session, flags overlaps before you collide, and suggests the next step.
- Hand a decision across with one printed relay line (harness menu: Share). You paste it where you already talk. collabai never sends anything itself.
- Get warned when fetched Git changes touch your files (`git-fetch`, `git-check`).

It costs a few short commands, adds zero tokens when there is nothing relevant, and fails gracefully: if collabai is absent, your agents work exactly as before.

## Install (60 seconds)

Requires Python 3.11+. No sudo. Installs to `~/.local/bin`.

```bash
curl -fsSL https://github.com/wragorg/collabai/releases/latest/download/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
collabai --version
```

Pin an exact version instead:

```bash
curl -fsSL https://github.com/wragorg/collabai/releases/latest/download/install.sh | sh -s -- --version 1.0.1
```

Prefer to read before you run? Download first:

```bash
curl -fsSL https://github.com/wragorg/collabai/releases/download/v1.0.1/install.sh -o install.sh
# inspect install.sh, then:
sh install.sh --version 1.0.1
```

The installer downloads the release tarball and its `.sha256` over HTTPS, verifies the checksum before extracting (fail-closed), and writes a `~/.local/bin/collabai` shim. Upgrading is the same command with a newer `--version`. Removing is `collabai uninstall --yes` (private state only) plus deleting the shim and version directory.

If you run from a checkout instead (for example as user `dev` with the repo at `/root/collabai`):

```bash
export PYTHONPATH=/root/collabai:${PYTHONPATH:-}
python3 -m collabai --version
```

## Your first pair session (5 minutes)

Two developers, two machines. Dev A on a Mac with Claude Code, Dev B in Linux with Codex. Same project on both sides.

One-time setup per machine:

```bash
collabai init
collabai adapter-claude-install   # Dev A (Claude Code hook)
collabai adapter-codex-install    # Dev B (Codex AGENTS.md block)
```

Beat 1 — a decision crosses sessions without copy-paste:

```bash
# Dev A, in their own words:
collabai remember --task "Auth redesign" --area auth --files "auth/login.py" \
  --text "Use session cookies, not local tokens" --agent claude-code --decision
# Dev B, from their own session:
collabai context --files "auth/login.py"
```

Unrelated files print nothing (zero added tokens). Secret-shaped input is refused.

Beat 2 — Git awareness across machines. Dev A commits and pushes as usual. Dev B, on a different network, runs:

```bash
collabai git-fetch
collabai git-check
```

Dev B gets warned only when the fetched changes touch files or areas with known local context. Stale assumptions get flagged before the two of you collide in `auth`.

Beat 3 — Collab Bot and the relay line. Either developer runs plain `collabai` and picks Share: Collab Bot prints one relay line for the last decision. Paste it into whatever channel you already use (chat, issue, email). The other side records it locally with Remember. Human-in-the-loop by design. Open Collab Bot (menu 1) any time to see both local sessions, overlaps first, with one suggested next step.

OpenCode has no dedicated adapter yet: it works through the same `context` / `remember` commands run by hand. Treat that path as an unproven fallback until a hook proof exists.

## Commands

| Command | It does |
|---|---|
| `init`, `status`, `doctor` | Set up and inspect local state |
| `remember`, `context` | Save and recall short notes |
| `decide` | Record an approved choice |
| `bot` | Collab Bot panel across sessions |
| `git-fetch/git-check` | Explicit fetch, relevance warn |
| `uninstall --yes` | Remove private state only |

## Privacy defaults

- Transcripts, diffs, prompts, secrets: never captured, never transmitted.
- Memory is local-only in gitignored `.collabai/` (`0700`/`0600`).
- No network listener runs by default. Live Share is deferred (see Roadmap).
- Git fetch is opt-in. Telemetry and extra inference are disabled.
- Anything your agent injects reaches your chosen model provider. That is the one boundary collabai cannot draw for you. See [docs/privacy-threat-model.md](docs/privacy-threat-model.md).

## Troubleshooting

- `collabai: command not found` — add `~/.local/bin` to `PATH`.
- `not initialized` — run `collabai init` in the project root first (or just run `collabai`; the first-run wizard offers setup).
- Harness looks wrong in a pipe — it falls back to numbered picks automatically when there is no TTY. Use the raw subcommands for scripting.
- Running from a checkout — export `PYTHONPATH` to the repo root as shown above.

## Roadmap

- **Live Share (deferred).** Temporary loopback sessions with SSH join. The loopback core and hardening are built; it returns only when the two-network transport story (mesh vs public SSH) is designed and proven end-to-end. The `live` subcommands still run today with a deferred notice, but no current docs depend on them. See [docs/ssh-tunnel.md](docs/ssh-tunnel.md), kept as a roadmap reference.

Status: v1.0.0. Python 3.11+ stdlib only. Apache-2.0.
