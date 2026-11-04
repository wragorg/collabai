# collabai

Two humans. Two AI coding agents. One shared memory.

collabai is a local-first companion for human-to-human pair programming across different AI coding agents. You keep your own agent — Claude Code, Codex, or anything else via the plain CLI. collabai carries the approved, structured knowledge between you: decisions, context, Git awareness, and an opt-in live channel. No extra LLM. No daemon. No cloud backend. No transcripts, diffs, or prompts ever leave your machine unless you explicitly post a short metadata event.

## Why download it

You and your pair each work in your own agent session, possibly on different machines. Without collabai, every decision has to be re-explained, re-pasted, and re-discovered in each session. With collabai:

- Record a decision once (`remember`, `decide`). Your partner recalls it from their own agent with one command.
- See at a glance what everyone is working on (`bot`). Pip, the terminal companion, shows each session, flags overlaps before you collide, and suggests the next step.
- Pair live across machines (`live`). One developer hosts on loopback; the other joins through their own SSH tunnel. Short metadata events only — never code, never transcripts.
- Get warned when fetched Git changes touch your files (`git-fetch`, `git-check`).

It costs a few short commands, adds zero tokens when there is nothing relevant, and fails gracefully: if collabai is absent, your agents work exactly as before.

## Install (60 seconds)

Requires Python 3.11+. No sudo. Installs to `~/.local/bin`.

```bash
curl -fsSL https://github.com/wragorg/collabai/releases/latest/download/install.sh -o install.sh
# inspect install.sh, then:
sh install.sh --version 1.0.0
export PATH="$HOME/.local/bin:$PATH"
collabai --version
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

Beat 2 — live across machines. Dev A hosts:

```bash
collabai live host --port 8797
```

The host prints the port, a one-time token, the expiry time, and a ready-to-paste join command. Dev B runs that `ssh -L` tunnel on their own machine with their own login, then:

```bash
COLLABAI_TOKEN='<paste-token>' collabai live feed --port 8797
COLLABAI_TOKEN='<paste-token>' collabai bot --port 8797
```

Dev B's `task.started` post appears on Dev A's feed as bannered untrusted data. Ctrl-C on the host revokes everything instantly. See [docs/ssh-tunnel.md](docs/ssh-tunnel.md) for the full walkthrough.

Beat 3 — Git awareness and Pip. Either developer runs `collabai git-fetch` then `collabai git-check` to get warned only when fetched changes touch known files. Either runs `collabai bot` to see both sessions, overlaps first, with Pip's suggested next step.

OpenCode has no dedicated adapter yet: it works through the same `context` / `remember` commands run by hand. Treat that path as an unproven fallback until a hook proof exists.

## Commands

| Command | It does |
|---|---|
| `init`, `status`, `doctor` | Set up and inspect local state |
| `remember`, `context` | Save and recall short notes |
| `decide` | Record an approved choice |
| `bot` | Pip panel across sessions |
| `live host/post/feed` | Temporary live sharing |
| `git-fetch/git-check` | Explicit fetch, relevance warn |
| `uninstall --yes` | Remove private state only |

## Privacy defaults

- Transcripts, diffs, prompts, secrets: never captured, never transmitted.
- Memory is local-only in gitignored `.collabai/` (`0700`/`0600`).
- Live Share is disabled by default, loopback-only, 15-minute in-memory token, auth on every endpoint, strict event schema. Remote events render as bannered untrusted data.
- Git fetch is opt-in. Telemetry and extra inference are disabled.
- Anything your agent injects reaches your chosen model provider. That is the one boundary collabai cannot draw for you. See [docs/privacy-threat-model.md](docs/privacy-threat-model.md).

## Troubleshooting

- `collabai: command not found` — add `~/.local/bin` to `PATH`.
- `not initialized` — run `collabai init` in the project root first.
- Feed says the tunnel is down — check your `ssh -L` terminal is still running, then re-run `live feed`.
- `401 unauthorized or expired` — the 15-minute session lapsed. Re-host with `live host`.
- Running from a checkout — export `PYTHONPATH` to the repo root as shown above.

Status: v1.0.0. Python 3.11+ stdlib only. Apache-2.0.
