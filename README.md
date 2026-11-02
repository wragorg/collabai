# collabai (formerly PairBridge)

Privacy-first collaboration for AI-assisted development. Local-first. No extra LLM. No daemon. No cloud backend.

Status: working CLI (`init`, `status`, `doctor`, `uninstall`, `remember`, `context`, `decide`, both adapters, Live Share, Git awareness). The `curl -fsSL` installer exists in `install.sh` (checksum-verified, `~/.local/bin`, no sudo) and awaits proof against the first public release. OpenCode has no dedicated adapter and stays an unproven CLI fallback (`context`/`remember` run by hand) until a hook PoC proves otherwise.

## Install (manual, for now)

Requires Python 3.11+.

```bash
python3 -m collabai init
python3 -m collabai status
python3 -m collabai doctor
```

## Privacy defaults

- Transcripts: never captured.
- Memory: local-only in `.collabai/` (gitignored, mode 0700/0600).
- Live Share: disabled by default.
- Git fetch: opt-in only.
- Telemetry and extra inference: disabled.

Injected context reaches your chosen model provider. See `docs/privacy-threat-model.md` (planned).
