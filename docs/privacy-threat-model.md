# Privacy and threat model (v2.1.0)

Defaults: transcripts never captured, memory local-only, Live Share off,
fetch opt-in off, telemetry off, no extra inference.

v2 additions, same rules:

- Agent questions (`ask`/`inbox`) are short, secret-scanned, stored
  `0600` in `.collabai/inbox/`, expire after 24 hours, and display as
  untrusted data. `watch` is foreground-only and opt-in; stopping it
  leaves nothing running.
- The Meta key (optional) is stored only at `~/.config/collabai/meta.key`
  (`0600`, outside any repo), never logged, and stripped from launched
  agents' environments. Meta AI extras are parked in 2.1.0: the model id
  and endpoint are unverified, so no AI call is made at all. When
  unparked, extras will send collabai metadata only (task names, areas,
  file names, decisions) — never file contents or transcripts.
- Self-update downloads release tarballs over HTTPS only and verifies
  `.sha256` fail-closed before extracting, like the installer.

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

Live Share boundaries (roadmap — deferred, not a shipped v1.0.0 workflow):

- `127.0.0.1` only. No LAN bind, no relay, no discovery. A second machine
  joins through its operator's own `ssh -L` tunnel (see `ssh-tunnel.md`).
- 15-minute in-memory token, auth on every endpoint, no logs of tokens or
  bodies. Host-header allowlist blocks DNS rebinding (`403`). Per-IP rate
  limit (`429`). Oversize bodies rejected (`413`). Expiry returns `401`.
- `/health` and `/feed` report `expires_in` so both sides can see the clock.
- Remote events are untrusted data: displayed under a banner, control
  characters stripped, never executed and never injected as instructions.

Disclosure: injected context reaches your chosen model provider. This
cannot be removed by collabai; it is minimised (context is capped at
~1,000 chars, empty when irrelevant, secret-scanned at write time) and
disclosed in `collabai doctor`, in both adapter installers, and in the
first-run wizard. Preview exactly what would be sent at any time with
`collabai context --files "<paths>"`. Unsigned or unreviewed install
scripts must be inspected before running — download the release script,
read it, verify the checksum step runs, then execute.
