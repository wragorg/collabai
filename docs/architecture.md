# Architecture (v2.0.0)

One stdlib-only Python CLI. No backend, no extra inference unless the developer adds a Meta key. Everything runs in the foreground while its command runs; the only background-shaped piece is `collabai watch`, started and stopped by hand.

- `collabai/cli.py` — argparse entry and thin handlers, including `--update` (checksum-verified self-update), `--uninstall` (per-component removal), and `--meta-key`.
- `collabai/harness.py` — the no-args menu. One screen, animation in the header, `@` file picker over project file names.
- `collabai/memory.py` — JSONL in `.collabai/memory/`, 7-day ephemeral expiry, secret and path refusal at write time.
- `collabai/bot.py` — Collab Bot: foreground panel over local records plus optional live peers. Overlaps first, one suggested next step per refresh. Never posts or sends.
- `collabai/notify.py` — agent question inbox in `.collabai/inbox/`: short, secret-scanned, 24-hour expiry, answered in the harness. `watch` polls it in the foreground.
- `collabai/agents.py` — launch `claude`/`codex`/`muse` from the harness: terminal hand-over, or an experimental line relay where the developer types every answer and approval. The Meta key is stripped from the child environment.
- `collabai/meta_ai.py` — optional Meta AI extras. Key at `~/.config/collabai/meta.key` (`0600`, outside any repo), default model `meta-spark-1.3`, metadata-only inputs, nothing auto-saved.
- `collabai/games.py` — Snake and a typing sprint; best scores in `.collabai/games.json`. A waiting question pauses play.
- `collabai/updater.py` — release download over HTTPS only, `.sha256` verified fail-closed, old install restored on failure.
- `collabai/adapters/claude.py` — SessionStart hook in `.claude/settings.local.json`.
- `collabai/adapters/codex.py` — managed block in root `AGENTS.md`, including the `ask`/`inbox` question flow.
- `collabai/live/` — DEFERRED (roadmap). Loopback-only host, token auth on all endpoints, strict event schema, `expires_in` on health and feed, paste-ready SSH join output on the host.
- `collabai/git_awareness.py` — explicit fetch plus relevance check.

Privacy is structural: empty context costs zero tokens, secrets are refused at write time and on the wire, agent questions and remote events render as bannered untrusted data, and collabai never sends anything across sessions itself.
