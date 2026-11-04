# Demo — two developers, two different agents

Developer A runs Claude Code on authentication. Developer B runs Codex on something that touches authentication. Both keep their own agent; collabai only bridges approved, structured knowledge. Use synthetic code only — never real prompts, tokens, or sources in the recording.

## Setup (each machine, once)

```bash
collabai init
collabai adapter-claude-install   # Dev A (Claude Code)
collabai adapter-codex-install    # Dev B (Codex)
```

Dev A's next Claude Code session gets a `SessionStart` hook that injects shared context only when relevant. Dev B's Codex reads the `AGENTS.md` block and recalls via CLI. OpenCode has no dedicated adapter yet; Dev B on OpenCode runs the same `context`/`remember` commands directly.

## Beat 1 — decision continuity

A records an approved decision. B recalls it without copying the conversation.

```bash
# Dev A
collabai remember --task "Auth redesign" --area auth --files "auth/login.py" --text "Use session cookies, not local tokens" --agent claude-code --decision
# Dev B
collabai context --files "auth/login.py"
```

Show that `context --files "unrelated/billing.py"` prints nothing (zero added tokens) and a secret `remember` is refused.

## Beat 2 — stay in the harness

Dev B opens `collabai` and picks Launch (7) to run Codex without leaving collabai. The agent needs a decision and leaves a question instead of blocking:

```bash
collabai ask --agent codex --question "Session cookies or local tokens?" --options "cookies|tokens"
```

The harness banner shows the waiting question. Dev B picks Inbox (2), chooses `cookies`, and keeps working. The agent reads the answer with `collabai inbox --answer <id>`. Only the question and answer text crossed — no code, diffs, prompts, or transcripts. `collabai watch` does the same notification job in a foreground window.

While waiting, Dev B picks Games (11) for a round of Snake; a new agent question pauses the game.

## Beat 3 — Git warning, then privacy close

A commits and pushes from a test repo. B runs `collabai git-fetch`, then `git-check` (or menu 9). Show the warning only when a relevant file changed. Close on privacy: private memory stayed in gitignored `.collabai/`, the Meta key (if used) stayed outside the repo, file paths were shared only after explicit posting, and disconnecting deleted nothing locally.
