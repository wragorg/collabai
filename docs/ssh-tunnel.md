# SSH tunnel guide (manual, optional)

Live Share binds `127.0.0.1` only. For a second machine, that machine's
operator creates their own SSH tunnel. Nothing is exposed publicly.

## Host side (sharing developer)

1. Start the host: `python3 -m collabai live host`.
2. Note the printed port. Share the port and token with one invited
   developer over a trusted channel. Never commit or log them.
3. Stop with Ctrl-C when done. The token is revoked.

## Join side (joining developer, their own command)

```bash
ssh -o StrictHostKeyChecking=yes -o ExitOnForwardOnly=yes -N \
  -i ~/.ssh/collabai-forward \
  -L <LOCAL_PORT>:127.0.0.1:<HOST_PORT> <host-user>@<host-address>
```

Verify the host key on first connect. If the key ever changes, stop and
contact the host developer out of band — do not bypass the warning.

Then in a second terminal:

```bash
export COLLABAI_TOKEN="<invited-token>"
python3 -m collabai live feed --port <LOCAL_PORT>
```

Rules:

- Never disable host-key checking (`StrictHostKeyChecking=no` is forbidden).
- Prefer a dedicated forwarding-only key on the host:

```text
restrict,port-forwarding,permitopen="127.0.0.1:<HOST_PORT>" <key>
```

- That key cannot open a shell. It forwards to one loopback port only.
- Full-shell SSH access is never required.
- Revoke by stopping `live host` and removing the key.
