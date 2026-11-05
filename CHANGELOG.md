# Changelog

## 2.2.1

- Fixed: TLS certificate failures (macOS Python with no CA bundle) now
  print one mapped line naming the cause and the `Install
  Certificates.command` fix, instead of a generic `Meta call failed`.
  Verification is never disabled.

## 2.2.0

- Fixed: Meta model id corrected from the never-valid `meta-spark-1.3`
  to `muse-spark-1.3` (Meta Model API docs); stored legacy configs are
  migrated automatically. HTTP failures now print one mapped line
  (401 key, 400/404 model, 429 rate limit) instead of a generic error.
- Added: `collabai --meta-test` (one minimal call that proves key +
  model + endpoint; owner-pasted result: `meta-test: ok (ready)`) and
  a menu-8 multi-turn chat loop (`meta>` prompt, history resent per
  turn, `/clear`, `/save`, `/note`, `/overlap`, `/standup`,
  `/fortune`). Installer offers the Meta key again.

## 2.1.0

Professional-release cleanup. No new daemon, no new dependencies
(Python 3.11+ stdlib only).

- Removed: experimental line-relay launch (`launch --relay`, harness
  `[r]` option). Its pipes are not a TTY, so TTY-requiring agents
  (notably `claude`) exited immediately. Terminal hand-over is the only
  supported launch mode; questions arriving during hand-over are now
  flagged when the agent exits.
- Added: `collabai ask --wait [--timeout SECONDS]` and
  `collabai inbox --answer <id> --wait [--timeout SECONDS]`. The agent
  waits in the foreground for the developer's answer (exit 0 = answer
  printed, exit 2 = timeout/expired, exit 1 = error). The Codex
  `AGENTS.md` block teaches this flow and now upgrades in place when it
  changes. collabai still cannot push into a running agent session.
- Parked: Meta AI extras. The model id (`meta-spark-1.3`) and endpoint
  are unverified, so menu 8 explains and no AI call is made
  (`META_VERIFIED = False` in `collabai/meta_ai.py`). Key storage is
  unchanged. Unpark only with an owner-pasted live smoke call.
- Disclosure: the model-provider boundary for injected context is now
  printed by `collabai doctor`, both adapter installers, and the
  first-run wizard, with the preview command.
- Docs: beta note replaced by stated known limits; stale game/relay
  references removed.

Verification status at tagging time: see the release notes. Nothing in
this release is claimed verified without owner-pasted terminal output.

## 2.0.0

v2 feature set: self-update/uninstall, `@` file picker, one-screen
harness with top animation and alerts, agent question inbox with opt-in
foreground watcher, in-harness agent launch, optional Meta AI extras,
installer checksum fix (compare hashes directly, fail closed).

## 1.0.1

First published release: memory/context store, Claude and Codex
adapters, Git awareness, harness save → Share relay → Recall proven
across two machines.
