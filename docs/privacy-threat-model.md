# Privacy and threat model (MVP)

Defaults: transcripts never captured, memory local-only, Live Share off,
fetch opt-in off, telemetry off, no extra inference.

Boundaries:

- `.collabai/` is gitignored, `0700`/`0600`. Review before committing anything.
- `context` output is capped (~1,000 chars) and empty when irrelevant.
- `remember`/`decide` refuse secret-shaped input; file paths need allowlisting
  judgment since names can leak intent.
- Live Share: `127.0.0.1` only, 15-minute token in memory, auth everywhere,
  no logs of tokens or bodies, banned fields rejected, stop revokes instantly.
- Remote events are untrusted data: displayed, never executed or injected as
  instructions.

Disclosure: injected context reaches your chosen model provider. Unsigned
install scripts must be inspected before piping to shell.
