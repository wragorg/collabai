"""Bot (Pip) tests (stdlib unittest only). Owner-run: python3 -m unittest discover -s tests -v."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from collabai.bot import build_snapshot, burst, mood_for, render_panel, spin_frame

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


if __name__ == "__main__":
    unittest.main()
