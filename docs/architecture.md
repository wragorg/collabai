# Architecture (MVP)

One stdlib-only Python CLI. No daemon, no backend, no extra LLM.

- `collabai/cli.py` — argparse commands only.
- `collabai/memory.py` — JSONL in `.collabai/memory/`, 7-day ephemeral expiry.
- `collabai/adapters/claude.py` — SessionStart hook in `.claude/settings.local.json`.
- `collabai/adapters/codex.py` — managed block in root `AGENTS.md`.
- `collabai/live/` — loopback-only host, token auth on all endpoints.
- `collabai/git_awareness.py` — explicit fetch plus relevance check.

Privacy is structural: empty output costs zero tokens, secrets are refused
at write time, and Live Share transmits only events you explicitly post.
