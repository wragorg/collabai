# Demo (two developers, two machines, synthetic)

Dev A on a Mac with Claude Code. Dev B on Linux with Codex. Same project on
both sides. Use synthetic notes only — never real prompts, tokens, or sources.

## Setup (each machine, once)

```bash
collabai init
collabai adapter-claude-install   # Dev A (Claude Code)
collabai adapter-codex-install    # Dev B (Codex)
```

Dev A's next Claude Code session gets a `SessionStart` hook that injects
shared context only when relevant. Dev B's Codex reads the `AGENTS.md` block
and recalls via CLI. OpenCode has no dedicated adapter; it runs the same
`context` / `remember` commands by hand (unproven fallback).

## Scenario 1 — a decision crosses sessions

```bash
# Dev A, in their own words:
collabai remember --task "Auth redesign" --area auth --files "auth/login.py" \
  --text "Use session cookies, not local tokens" --agent claude-code --decision
# Dev B, from their own session:
collabai context --files "auth/login.py"
```

Show that `context --files "unrelated/billing.py"` prints nothing (zero added
tokens) and that a secret `remember` is refused.

## Scenario 2 — live across machines

```bash
# Dev A (Mac): collabai live host --port 8797   (prints port + token + join line)
# Dev B (Linux): ssh -L 8797:127.0.0.1:8797 <you>@<mac-host>   (own login, keep running)
# Dev B: COLLABAI_TOKEN='<paste-token>' collabai live post --port 8797 \
#          --type task.started --developer "Dev B" --task "Billing reads session user" \
#          --area auth --status in_progress
# Dev A: COLLABAI_TOKEN='<paste-token>' collabai live feed --port 8797
# Either: collabai bot --port 8797
```

Only posted metadata crossed. No code, diffs, prompts, or transcripts.
Ctrl-C on the host revokes the token instantly and agents keep working.

## Scenario 3 — Pip sees both sides

With the tunnel up, `collabai bot --port 8797` shows local sessions and the
remote developer in one table, overlaps on top, and one suggested next step.
Press `r` for the manual relay line, `Enter` to refresh, `q` to quit. Pip
never posts or sends anything itself.

## Scenario 4 — Git warning, then privacy close

Dev A commits and pushes from a test repo. Dev B runs an explicit
`git-fetch`, then `git-check`. Show the warning only when a relevant file
changed. Close on privacy: memory stayed in gitignored `.collabai/`, paths
were shared only after explicit posting, expiry is visible in the feed, and
disconnecting deleted nothing locally.
