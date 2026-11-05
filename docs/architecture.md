# Architecture (v2.2.0)

One stdlib-only Python CLI. No backend, no extra inference unless the developer adds a Meta key. Everything runs in the foreground while its command runs; the only background-shaped piece is `collabai watch`, started and stopped by hand.

- `collabai/cli.py` — argparse entry and thin handlers, including `--update` (checksum-verified self-update), `--uninstall` (per-component removal), and `--meta-key`.
- `collabai/harness.py` — the no-args menu. One screen, animation in the header, `@` file picker over project file names.
- `collabai/memory.py` — JSONL in `.collabai/memory/`, 7-day ephemeral expiry, secret and path refusal at write time.
- `collabai/bot.py` — Collab Bot: foreground panel over local records plus optional live peers. Overlaps first, one suggested next step per refresh. Never posts or sends.
- `collabai/notify.py` — agent question inbox in `.collabai/inbox/`: short, secret-scanned, 24-hour expiry, answered in the harness. `ask --wait` / `inbox --answer <id> --wait` poll for the answer in the foreground (no daemon; exit 2 on timeout). `watch` polls it in the foreground.
- `collabai/agents.py` — launch `claude`/`codex`/`muse` from the harness by terminal hand-over only (the line relay was removed in 2.1.0; it could not drive TTY agents). The Meta key is stripped from the child environment; questions arriving during hand-over are flagged on exit.
- `collabai/meta_ai.py` — Meta Model API client, model `muse-spark-1.3`, verified live by an owner-pasted `collabai --meta-test` (`ok (ready)`). Menu 8 is a multi-turn `meta>` chat loop. Key storage at `~/.config/collabai/meta.key` (`0600`, outside any repo) is unchanged.
- `collabai/updater.py` — release download over HTTPS only, `.sha256` verified fail-closed, old install restored on failure.
- `collabai/adapters/claude.py` — SessionStart hook in `.claude/settings.local.json`.
- `collabai/adapters/codex.py` — managed block in root `AGENTS.md`, including the `ask`/`inbox` question flow.
- `collabai/live/` — DEFERRED (roadmap). Loopback-only host, token auth on all endpoints, strict event schema, `expires_in` on health and feed, paste-ready SSH join output on the host.
- `collabai/git_awareness.py` — explicit fetch plus relevance check.

Privacy is structural: empty context costs zero tokens, secrets are refused at write time and on the wire, agent questions and remote events render as bannered untrusted data, and collabai never sends anything across sessions itself.
