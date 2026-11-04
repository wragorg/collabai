# Architecture (v1.0.0)

One stdlib-only Python CLI. No daemon, no backend, no extra LLM.

- `collabai/cli.py` — argparse commands only, thin handlers.
- `collabai/memory.py` — JSONL in `.collabai/memory/`, 7-day ephemeral expiry,
  secret and path refusal at write time.
- `collabai/bot.py` — Collab Bot: foreground panel over local records plus optional
  live peers. One table (local `L`, remote `R`), overlaps first, orbit beacon
  by session count, one suggested next step per refresh. Never posts or sends.
- `collabai/adapters/claude.py` — SessionStart hook in `.claude/settings.local.json`.
- `collabai/adapters/codex.py` — managed block in root `AGENTS.md`.
- `collabai/live/` — DEFERRED (roadmap). Loopback-only host, token auth on all endpoints, strict
  event schema (known keys only, length / control-char / secret checks),
  `expires_in` on health and feed, paste-ready SSH join output on the host.
- `collabai/git_awareness.py` — explicit fetch plus relevance check.

Privacy is structural: empty output costs zero tokens, secrets are refused
at write time and on the wire, and Live Share transmits only events you
explicitly post. Remote events render as bannered untrusted data.
