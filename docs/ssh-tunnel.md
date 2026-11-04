# SSH tunnel guide (two machines, one loopback)

> **Roadmap reference — not a current v1.0.0 capability.** Live Share is
> deferred. This guide is kept for the revival design only. The `live`
> subcommands still run locally with a deferred notice.

Live Share binds `127.0.0.1` only and never listens on any network. A second
machine joins by forwarding a local port to the host's loopback through SSH.
Nothing is exposed publicly. The host below runs on either machine; the worked
example hosts on the Mac (Claude Code side) and joins from Linux (Codex side).
Either direction works the same.

## Host side (sharing developer)

1. Start the host: `collabai live host --port 8797` (or `--port 0` for an
   ephemeral port).
2. The host prints the port, a one-time token, the UTC expiry time, and a
   ready-to-paste join command. It looks like this:

```text
port: 8797
token: <one-time-token>
expires at (UTC): 2026-11-04T12:15:00Z
Joiner command (run on THEIR machine, their own SSH login):
  ssh -L 8797:127.0.0.1:8797 <you>@<this-host>
```

3. Share the port and token with one invited developer over a trusted
   channel. Never commit, log, or paste them where others can see.
4. Stop with Ctrl-C when done. The token is revoked immediately. Sessions
   expire after 15 minutes in any case; re-host when you need more time.

## Join side (joining developer, their own commands)

Keep this terminal running for the whole session:

```bash
ssh -N -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -L 8797:127.0.0.1:8797 <you>@<this-host>
```

Verify the host key on first connect. If the key ever changes, stop and
contact the host developer out of band — do not bypass the warning.

Then in a second terminal:

```bash
COLLABAI_TOKEN='<paste-token>' collabai live feed --port 8797
COLLABAI_TOKEN='<paste-token>' collabai bot --port 8797
```

Post your presence so the host sees you:

```bash
COLLABAI_TOKEN='<paste-token>' collabai live post --port 8797 \
  --type developer.joined --developer "<your-name>" --area "<area>"
```

Rules:

- The token travels via environment or hidden prompt only. It never appears
  as a `--token` flag (it would show in `ps`).
- Never disable host-key checking (`StrictHostKeyChecking=no` is forbidden).
- Prefer a dedicated forwarding-only key on the host:

```text
restrict,port-forwarding,permitopen="127.0.0.1:8797" <key>
```

- That key cannot open a shell. It forwards to one loopback port only.
- Full-shell SSH access is never required.
- Revoke by stopping `live host` and removing the key.

## If something breaks

- `request failed ... tunnel down?` — your `ssh -L` terminal dropped.
  Reconnect it, then retry the command.
- `401 unauthorized or expired` — wrong token, or the 15-minute session
  lapsed. Ask the host to re-host for a fresh token.
- `live session expires in ~N min` after a feed — plan your re-host before
  it hits zero. There is no auto-renew by design.
- `429 rate limited` — slow down; the bucket is 60 requests per minute per IP.
