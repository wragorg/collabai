"""Harness tests (stdlib unittest only). Owner-run: python3 -m unittest tests.test_harness -v."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from collabai.harness import render_idle, render_menu, render_splash, run_harness
from collabai.memory import load_records


def _scripted(lines: list[str]):
    it = iter(lines)

    def _fn(_prompt: str = "") -> str:
        try:
            return next(it)
        except StopIteration:
            raise EOFError

    return _fn


def _preset_config(root: Path) -> None:
    state = root / ".collabai"
    state.mkdir(parents=True, exist_ok=True)
    (state / "config.json").write_text("{}\n", encoding="utf-8")


def _run(root: Path, lines: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = run_harness(root, input_fn=_scripted(lines))
    assert rc == 0
    return buf.getvalue()


class HarnessRenderTests(unittest.TestCase):
    def test_menu_is_retro_and_humans_only(self):
        menu = render_menu("1.0.0")
        self.assertIn("C O L L A B A I", menu)
        self.assertIn("RIGHT NOW", menu)
        self.assertIn("DO SOMETHING", menu)
        self.assertIn("CHECK", menu)
        self.assertIn("See who's doing what", menu)
        self.assertIn("(Collab Bot)", menu)
        self.assertIn("(Share)", menu)
        self.assertIn("(Quit)", menu)
        self.assertNotIn("\x1b", menu)
        self.assertNotIn("Pair", menu)
        self.assertNotIn("ssh", menu)

    def test_menu_shows_suggestion_and_color_only_when_asked(self):
        plain = render_menu("1.0.0", suggest="check auth")
        self.assertIn("Collab Bot suggests: check auth", plain)
        fancy = render_menu("1.0.0", color=True)
        self.assertIn("\x1b[", fancy)

    def test_splash_shows_collab_bot(self):
        self.assertIn("Collab Bot", render_splash("1.0.0"))

    def test_idle_line_is_minimal_and_gated(self):
        plain = render_idle(0)
        self.assertIn("Collab Bot", plain)
        self.assertIn(">", plain)
        self.assertNotIn("\x1b", plain)
        fancy = render_idle(0, color=True)
        self.assertIn("\x1b[36m", fancy)
        self.assertNotEqual(render_idle(0), render_idle(1))


class LiveParkTests(unittest.TestCase):
    def test_live_handlers_announce_deferred(self):
        import argparse
        import io
        from contextlib import redirect_stderr

        from collabai.cli import cmd_live_host

        err = io.StringIO()
        with redirect_stderr(err):
            rc = cmd_live_host(argparse.Namespace(port=80))
        self.assertEqual(rc, 1)
        self.assertIn("deferred (roadmap)", err.getvalue())


class HarnessFlowTests(unittest.TestCase):
    def test_wizard_decline_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = _run(root, ["n", "11"])
            self.assertIn("bye", out)
            self.assertFalse((root / ".collabai").exists())

    def test_remember_then_share(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _preset_config(root)
            out = _run(root, [
                "3", "Auth redesign", "auth/login.py", "auth",
                "Use session cookies", "claude-code", "y", "", "",
                "6", "", "11",
            ])
            self.assertIn("[collabai]", out)
            self.assertIn("Use session cookies", out)
            recs = load_records(root)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["kind"], "decision")

    def test_decide_rejects_single_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _preset_config(root)
            out = _run(root, ["5", "Pick storage?", "OnlyOne", "", "11"])
            self.assertIn("give 2-3 alternatives", out)
            self.assertEqual(load_records(root), [])

    def test_quit_with_q(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _preset_config(root)
            out = _run(root, ["q"])
            self.assertIn("bye for now", out)


if __name__ == "__main__":
    unittest.main()
