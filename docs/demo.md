# Demo (two developers, synthetic)

Scenario 1 — recall:

```bash
python3 -m collabai remember --task "Auth redesign" --area auth --files "auth/login.py" --text "Use session cookies" --agent claude-code --decision
python3 -m collabai context --files "auth/login.py"
```

Scenario 2 — live (two terminals, one machine):

Terminal A: `python3 -m collabai live host`.
Terminal B: `COLLABAI_TOKEN=... python3 -m collabai live post --port ... --type task.started --developer "Dev A" --task "Auth redesign" --area auth --status in_progress`, then `live feed`.

Scenario 3 — git: `python3 -m collabai git-fetch`, then `python3 -m collabai git-check`.

Scenario 4 — privacy: unrelated `context` prints nothing, secret `remember`
is refused, wrong-token feed is `401`, Ctrl-C revokes the session.
