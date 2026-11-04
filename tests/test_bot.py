"""Bot (Pip) tests (stdlib unittest only). Owner-run: python3 -m unittest discover -s tests -v."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from collabai.bot import (
    build_peer_rows,
    build_snapshot,
    burst,
    mood_for,
    next_hint,
    orbit_beacon,
    render_panel,
    spin_frame,
)

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


def _rec(agent: str, area: str, hours_ago: int = 0, kind: str = "ephemeral",
         task: str = "work", text: str = "note") -> dict:
    ts = (NOW - timedelta(hours=hours_ago)).isoformat(timespec="seconds")
    return {"id": f"{agent}-{area}-{hours_ago}", "ts": ts, "agent": agent,
            "task": task, "area": area, "files": [], "kind": kind,
            "text": text, "shareable": False, "expires_at": None}


class BotSnapshotTests(unittest.TestCase):
    def test_overlap_detected(self):
        snap = build_snapshot([
            _rec("claude-code", "auth"),
            _rec("codex", "auth"),
            _rec("codex", "billing", hours_ago=1),
        ])
        self.assertEqual(set(snap["overlaps"]), {"auth"})
        self.assertEqual(snap["overlaps"]["auth"], ["claude-code", "codex"])

    def test_empty_snapshot(self):
        snap = build_snapshot([])
        self.assertEqual(snap["agents"], [])
        key, face, _ = mood_for(snap, now=NOW)
        self.assertEqual((key, face), ("sleepy", "(-_-)zZ"))
        self.assertIn("no sessions yet", render_panel(snap, tty=False, now=NOW))

    def test_moods_from_metadata(self):
        overlap = build_snapshot([_rec("claude-code", "auth"), _rec("codex", "auth")])
        self.assertEqual(mood_for(overlap, now=NOW)[0], "overlap")
        stale = build_snapshot([_rec("codex", "billing", hours_ago=2)])
        self.assertEqual(mood_for(stale, now=NOW)[0], "sleepy")
        fresh = build_snapshot([_rec("claude-code", "auth")])
        self.assertEqual(mood_for(fresh, now=NOW)[0], "clear")
        done = [{"type": "task.completed", "developer": "Dev B", "task": "t",
                 "area": "auth", "status": "done", "seq": 1, "at": "2026-11-03T12:00:00Z"}]
        self.assertEqual(mood_for(fresh, done, now=NOW)[0], "celebrate")
        self.assertIn(burst(), mood_for(fresh, done, now=NOW)[2])

    def test_live_banner_strips_controls(self):
        snap = build_snapshot([_rec("claude-code", "auth")])
        events = [{"seq": 1, "at": "2026-11-03T12:00:00Z", "type": "task.started",
                   "developer": "Dev\x1b[31m B", "task": "t", "area": "auth", "status": "in_progress"}]
        panel = render_panel(snap, events, tty=False, now=NOW)
        self.assertIn("UNTRUSTED DATA", panel)
        self.assertNotIn("\x1b", panel)

    def test_plain_output_has_no_ansi(self):
        snap = build_snapshot([_rec("claude-code", "auth")])
        panel = render_panel(snap, tty=False, tick=1, now=NOW)
        self.assertNotIn("\033", panel)
        self.assertTrue(spin_frame(0, tty=False))

    def test_peer_rows_collapse_to_latest_per_developer(self):
        events = [
            {"seq": 1, "at": "2026-11-03T11:00:00Z", "type": "task.started",
             "developer": "Dev B", "task": "old", "area": "auth", "status": "in_progress"},
            {"seq": 2, "at": "2026-11-03T11:30:00Z", "type": "task.completed",
             "developer": "Dev B", "task": "new", "area": "auth", "status": "done"},
        ]
        peers = build_peer_rows(events)
        self.assertEqual(len(peers), 1)
        self.assertEqual(peers[0]["task"], "new")
        self.assertEqual(peers[0]["state"], "done")

    def test_panel_lists_local_and_remote_rows(self):
        snap = build_snapshot([_rec("claude-code", "auth")])
        events = [{"seq": 1, "at": "2026-11-03T11:30:00Z", "type": "task.started",
                   "developer": "Dev B", "task": "billing", "area": "auth",
                   "status": "in_progress"}]
        panel = render_panel(snap, events, tty=False, now=NOW)
        self.assertIn("L claude-code", panel)
        self.assertIn("R Dev B", panel)
        self.assertIn("1 local", panel)

    def test_orbit_beacon_shows_one_dot_per_session(self):
        ascii_two = orbit_beacon(2, 0, "clear", tty=False)
        ascii_five = orbit_beacon(5, 0, "clear", tty=False)
        self.assertEqual(ascii_two.count("o"), 1 + 2)
        self.assertEqual(ascii_five.count("o"), 1 + 5)
        self.assertNotEqual(
            orbit_beacon(2, 0, "clear", tty=False),
            orbit_beacon(2, 3, "clear", tty=False),
        )

    def test_next_hint_prioritizes_overlap_then_remote(self):
        overlap = build_snapshot([_rec("claude-code", "auth"), _rec("codex", "auth")])
        pid, say, cmd = next_hint(overlap, [])
        self.assertTrue(pid.startswith("overlap:"))
        self.assertIn("auth", cmd)
        solo = build_snapshot([_rec("claude-code", "billing")])
        peers = build_peer_rows([{"seq": 1, "at": "2026-11-03T11:30:00Z",
                                  "type": "developer.joined", "developer": "Dev B",
                                  "task": "", "area": "", "status": ""}])
        pid2, _, _ = next_hint(solo, peers)
        self.assertEqual(pid2, "remote:hello")

    def test_long_task_never_breaks_row_width(self):
        snap = build_snapshot([_rec("claude-code", "auth", task="x" * 200)])
        for line in render_panel(snap, tty=False, now=NOW).splitlines():
            self.assertLessEqual(len(line), 100)


if __name__ == "__main__":
    unittest.main()
