# Privacy and threat model (v1.0.0)

Defaults: transcripts never captured, memory local-only, Live Share off,
fetch opt-in off, telemetry off, no extra inference.

What is stored where:

- `.collabai/` is gitignored, directories `0700`, files `0600`. Review
  before committing anything. `uninstall --yes` removes this directory only.
- `context` output is capped (~1,000 chars, ~250 tokens) and empty when
  irrelevant. Empty costs your agent zero tokens.
- File paths are validated: absolute paths, `..` traversal, and secret
  filenames (`.env`, keys, certs) refuse the whole record.

What is refused:

- `remember` / `decide` refuse secret-shaped input across every field
  (private-key headers, cloud and provider tokens, JWTs, bearer strings,
  `password=` / `api_key=` style assignments). Nothing is stored.
- `live post` enforces the same fail-closed rule on the wire: only the keys
  `type`, `developer`, `task`, `area`, `status` are accepted. Unknown or
  banned fields (`code`, `diff`, `transcript`, `prompt`, `secret`, `token`),
  over-long values, control characters, and secret-shaped values are
  rejected with `400`. Nothing is stored.

Live Share boundaries:

- `127.0.0.1` only. No LAN bind, no relay, no discovery. A second machine
  joins through its operator's own `ssh -L` tunnel (see `ssh-tunnel.md`).
- 15-minute in-memory token, auth on every endpoint, no logs of tokens or
  bodies. Host-header allowlist blocks DNS rebinding (`403`). Per-IP rate
  limit (`429`). Oversize bodies rejected (`413`). Expiry returns `401`.
- `/health` and `/feed` report `expires_in` so both sides can see the clock.
- Remote events are untrusted data: displayed under a banner, control
  characters stripped, never executed and never injected as instructions.

Disclosure: injected context reaches your chosen model provider. Unsigned or
unreviewed install scripts must be inspected before running — download the
release script, read it, verify the checksum step runs, then execute.
