# collabai (formerly PairBridge)

Privacy-first collaboration for AI-assisted development. Local-first. No extra LLM. No daemon. No cloud backend.

Status: Day 1 MVP skeleton. `collabai init/status/doctor/uninstall` only. Memory, adapters, Live Share, and Git awareness land in later increments.

## Install (manual, for now)

Requires Python 3.11+.

```bash
python3 -m collabai init
python3 -m collabai status
python3 -m collabai doctor
```

A `curl -fsSL` installer is planned for release (Day 4). It will download a release tarball, verify it, install to `~/.local/bin`, and never need sudo. Not implemented yet.

## Privacy defaults

- Transcripts: never captured.
- Memory: local-only in `.collabai/` (gitignored, mode 0700/0600).
- Live Share: disabled by default.
- Git fetch: opt-in only.
- Telemetry and extra inference: disabled.

Injected context reaches your chosen model provider. See `docs/privacy-threat-model.md` (planned).
