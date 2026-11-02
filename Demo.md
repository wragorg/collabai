# Demo — two developers, two different agents

Developer A runs Claude Code on authentication. Developer B runs Codex (or
OpenCode) on something that touches authentication. Both keep their own agent;
`collabai` only bridges approved, structured knowledge. Use synthetic code
only — never real prompts, tokens, or sources in the recording.

## Setup (each machine, once)

```bash
python3 -m collabai init
python3 -m collabai adapter-claude-install   # Dev A (Claude Code)
python3 -m collabai adapter-codex-install    # Dev B (Codex)
```

Dev A’s next Claude Code session gets a `SessionStart` hook that injects
shared context only when relevant. Dev B’s Codex reads the `AGENTS.md` block
and recalls via CLI. OpenCode has no dedicated adapter yet; Dev B on OpenCode
runs the same `context`/`remember` commands directly.

## Beat 1 — decision continuity

A records an approved decision. B recalls it without copying the conversation.

```bash
# Dev A
python3 -m collabai remember --task "Auth redesign" --area auth --files "auth/login.py" --text "Use session cookies, not local tokens" --agent claude-code --decision
# Dev B
python3 -m collabai context --files "auth/login.py"
```

Show that `context --files "unrelated/billing.py"` prints nothing (zero added
tokens) and a secret `remember` is refused.

## Beat 2 — live collaboration (no remote needed)

```bash
# Dev A terminal: python3 -m collabai live host  (prints port + token once)
# Dev B terminal: COLLABAI_TOKEN=... python3 -m collabai live post --port <port> --type task.started --developer "Dev B" --task "Billing reads session user" --area auth --status in_progress
# Dev A terminal: COLLABAI_TOKEN=... python3 -m collabai live feed --port <port>
```

Only the posted metadata crossed. No code, diffs, prompts, or transcripts.
Ctrl-C on the host revokes the token instantly and agents keep working.

## Beat 3 — Git warning, then privacy close

A commits and pushes from a test repo. B runs an explicit `git-fetch`, then
`git-check`. Show the warning only when a relevant file changed. Close on
privacy: private memory stayed in gitignored `.collabai/`, file paths were
shared only after explicit posting, and disconnecting deleted nothing locally.
