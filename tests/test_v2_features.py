"""v2 feature tests (stdlib unittest, no network, no real agents).

Owner-run: python3 -m unittest discover -s tests -v
Covers the @ picker, the question inbox, games logic, Meta key storage,
and agent detection. Downloads and AI calls are never made here.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collabai import games, meta_ai, notify
from collabai.agents import looks_like_question
from collabai.harness import MENU, _files_prompt, list_project_files, render_top_line


def _scripted(lines):
    it = iter(lines)
    return lambda _prompt="": next(it)


class MenuOrderTests(unittest.TestCase):
    def test_numbers_sorted_in_display_order(self):
        self.assertEqual([int(k) for k, *_ in MENU], list(range(1, 13)))

    def test_top_line_animates_without_ansi_by_default(self):
        self.assertNotEqual(render_top_line(0), render_top_line(1))
        self.assertNotIn("\x1b", render_top_line(0))
        self.assertIn("Collab Bot", render_top_line(0))


class PickerTests(unittest.TestCase):
    def test_list_skips_private_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "auth").mkdir()
            (root / "auth" / "login.py").write_text("x", encoding="utf-8")
            (root / ".collabai").mkdir()
            (root / ".collabai" / "secret.json").write_text("x", encoding="utf-8")
            files = list_project_files(root)
            self.assertIn("auth/login.py", files)
            self.assertNotIn(".collabai/secret.json", files)

    def test_at_exact_path_selects_without_picker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("x", encoding="utf-8")
            picked = _files_prompt(root, _scripted(["@a.py"]))
            self.assertEqual(picked, ["a.py"])

    def test_at_filter_then_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "auth").mkdir()
            (root / "auth" / "login.py").write_text("x", encoding="utf-8")
            (root / "billing.py").write_text("x", encoding="utf-8")
            picked = _files_prompt(root, _scripted(["@auth", "1"]))
            self.assertEqual(picked, ["auth/login.py"])


class InboxTests(unittest.TestCase):
    def test_ask_answer_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rec = notify.ask_question(root, "codex", "Use cookies or tokens?",
                                      options=["cookies", "tokens"])
            pending = notify.list_pending(root)
            self.assertEqual([p["id"] for p in pending], [rec["id"]])
            self.assertIsNone(notify.read_answer(root, rec["id"]))
            notify.answer_question(root, rec["id"], "cookies")
            self.assertEqual(notify.read_answer(root, rec["id"]), "cookies")
            self.assertEqual(notify.list_pending(root), [])
            mode = oct((root / ".collabai" / "inbox" / f"q-{rec['id']}.json").stat().st_mode)
            self.assertTrue(mode.endswith("600"))

    def test_pending_alert_fires_once_per_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alerted: set[str] = set()
            self.assertEqual(notify.pending_alert(root, alerted), "")
            first = notify.ask_question(root, "codex", "Cookies or tokens?")
            text = notify.pending_alert(root, alerted)
            self.assertIn("1 agent question", text)
            self.assertIn("codex", text)
            self.assertEqual(notify.pending_alert(root, alerted), "")
            notify.answer_question(root, first["id"], "cookies")
            notify.ask_question(root, "claude", "Ship it?")
            self.assertIn("claude", notify.pending_alert(root, alerted))

    def test_secret_question_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                notify.ask_question(root, "codex", "password= hunter2 use it?")
            self.assertEqual(notify.list_pending(root), [])


class GamesTests(unittest.TestCase):
    def test_snake_eats_and_scores(self):
        game = games.SnakeGame(width=5, height=5, seed=1)
        game.food = (game.snake[0][0] + 1, game.snake[0][1])
        game.step()
        self.assertEqual(game.score, 1)
        self.assertEqual(len(game.snake), 2)

    def test_snake_wall_kills(self):
        game = games.SnakeGame(width=3, height=3, seed=1)
        for _ in range(5):
            game.step()
        self.assertFalse(game.alive)

    def test_snake_survives_opening_steps_on_wide_board(self):
        game = games.SnakeGame(width=26, height=14, seed=3)
        for _ in range(5):
            game.step()
        self.assertTrue(game.alive)


class MetaKeyTests(unittest.TestCase):
    def test_store_load_delete_with_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.dict(os.environ, {}, clear=True):
                self.assertIsNone(meta_ai.load_key(home=home))
                path = meta_ai.store_key("test-key-123", home=home)
                self.assertTrue(oct(path.stat().st_mode).endswith("600"))
                self.assertEqual(meta_ai.load_key(home=home), "test-key-123")
                self.assertTrue(meta_ai.delete_key(home=home))
                self.assertIsNone(meta_ai.load_key(home=home))

    def test_env_overrides_file_and_default_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            meta_ai.store_key("file-key", home=home)
            with patch.dict(os.environ, {"COLLABAI_META_API_KEY": "env-key"}):
                self.assertEqual(meta_ai.load_key(home=home), "env-key")
            self.assertEqual(meta_ai.model_for(Path(tmp)), "meta-spark-1.3")

    def test_chat_without_key_fails_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {}, clear=True), \
                    patch.object(meta_ai, "key_path", lambda home=None: Path(tmp) / "none"):
                with self.assertRaises(meta_ai.MetaError):
                    meta_ai.chat([{"role": "user", "content": "hi"}], Path(tmp))

    def test_whitespace_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                meta_ai.store_key("a b c", home=Path(tmp))


class AgentRelayTests(unittest.TestCase):
    def test_relay_survives_agent_exiting_immediately(self):
        import sys as _sys

        from collabai import agents

        with patch.dict(agents.AGENTS, {"claude": [_sys.executable, "-c", "pass"]}), \
                patch.object(agents.shutil, "which", lambda _exe: "/fake/claude"):
            code = agents.launch_agent(
                Path(tempfile.gettempdir()), "claude", relay=True,
                input_fn=lambda _prompt="": "create a fake report.md file here",
            )
        self.assertEqual(code, 0)

    def test_question_detection(self):
        self.assertTrue(looks_like_question("Allow this command? [y/N]"))
        self.assertTrue(looks_like_question("Which file should I edit?"))
        self.assertFalse(looks_like_question("done, all tests pass"))


if __name__ == "__main__":
    unittest.main()
