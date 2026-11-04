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

## Scenario 2 — Git warning across networks

Dev A commits and pushes from a test repo. Dev B, on a different network,
runs an explicit `git-fetch`, then `git-check`. Show the warning only when a
relevant file changed.

## Scenario 3 — Collab Bot and the relay line

Either developer runs `collabai` and picks Collab Bot (1): local sessions in
one table, overlaps on top, one suggested next step. Pick Share (5): Collab
Bot prints one relay line for the last decision. Dev B records it locally
with Remember. Press `Enter` to refresh, `q` to quit. Collab Bot never posts
or sends itself.
(Live Share presence is deferred — see the roadmap note in the README.)

## Scenario 4 — an agent asks, the developer stays put

Dev B launches Codex from the harness (menu 7). The agent leaves a short
question with `collabai ask`; the harness banner shows it, Dev B answers in
Inbox (menu 2), and the agent reads the answer back.

## Scenario 5 — privacy close

Close on privacy: memory stayed in gitignored `.collabai/`, nothing was
captured beyond approved notes, and stopping collabai changes nothing for
either agent.
