"""v2 feature tests (stdlib unittest, no network, no real agents).

Owner-run: python3 -m unittest discover -s tests -v
Covers the @ picker, the question inbox (including --wait), Meta key
storage and parking, hand-over launch, and the Codex block upgrade.
Downloads and AI calls are never made here.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collabai import meta_ai, notify
from collabai.harness import MENU, _files_prompt, list_project_files, render_top_line


def _scripted(lines):
    it = iter(lines)
    return lambda _prompt="": next(it)


class MenuOrderTests(unittest.TestCase):
    def test_numbers_sorted_in_display_order(self):
        self.assertEqual([int(k) for k, *_ in MENU], list(range(1, 12)))

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
            self.assertEqual(meta_ai.model_for(Path(tmp)), "muse-spark-1.3")

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


class AgentLaunchTests(unittest.TestCase):
    def test_handover_runs_agent_and_returns_its_code(self):
        import sys as _sys

        from collabai import agents

        with patch.dict(agents.AGENTS, {"claude": [_sys.executable, "-c", "pass"]}), \
                patch.object(agents.shutil, "which", lambda _exe: "/fake/claude"):
            code = agents.launch_agent(Path(tempfile.gettempdir()), "claude")
        self.assertEqual(code, 0)

    def test_handover_surfaces_pending_question_on_exit(self):
        import io
        import sys as _sys
        from contextlib import redirect_stdout

        from collabai import agents

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rec = notify.ask_question(root, "codex", "Cookies or tokens?")
            self.assertIsNotNone(rec)
            buf = io.StringIO()
            with patch.dict(agents.AGENTS, {"claude": [_sys.executable, "-c", "pass"]}), \
                    patch.object(agents.shutil, "which", lambda _exe: "/fake/claude"), \
                    redirect_stdout(buf):
                code = agents.launch_agent(root, "claude")
            self.assertEqual(code, 0)
            self.assertIn("agent question(s) waiting", buf.getvalue())

    def test_relay_flag_is_rejected(self):
        import argparse

        from collabai.cli import cmd_launch

        code = cmd_launch(argparse.Namespace(agent="claude", relay=True))
        self.assertEqual(code, 2)


class WaitForAnswerTests(unittest.TestCase):
    def test_wait_returns_existing_answer_immediately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rec = notify.ask_question(root, "codex", "Cookies or tokens?")
            notify.answer_question(root, rec["id"], "cookies")
            self.assertEqual(
                notify.wait_for_answer(root, rec["id"], timeout_seconds=0), "cookies")

    def test_wait_times_out_without_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rec = notify.ask_question(root, "codex", "Cookies or tokens?")
            self.assertIsNone(
                notify.wait_for_answer(root, rec["id"], timeout_seconds=0))

    def test_wait_returns_answer_that_arrives_while_waiting(self):
        import threading

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rec = notify.ask_question(root, "codex", "Cookies or tokens?")
            timer = threading.Timer(
                0.2, lambda: notify.answer_question(root, rec["id"], "tokens"))
            timer.start()
            try:
                self.assertEqual(
                    notify.wait_for_answer(root, rec["id"], timeout_seconds=5,
                                           poll_seconds=0.05),
                    "tokens")
            finally:
                timer.cancel()

    def test_wait_unknown_question_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(notify.has_question(root, "nope"))
            self.assertIsNone(
                notify.wait_for_answer(root, "nope", timeout_seconds=0))

    def test_inbox_wait_unknown_id_is_error(self):
        import argparse

        from collabai.cli import cmd_inbox

        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(Path, "cwd", classmethod(lambda cls: Path(tmp))):
            code = cmd_inbox(argparse.Namespace(
                answer="nope", wait=True, timeout=0.0))
        self.assertEqual(code, 1)


class CodexBlockUpgradeTests(unittest.TestCase):
    def test_apply_upgrades_old_block_and_preserves_user_content(self):
        from collabai.adapters import codex

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text(
                "# mine\n\n<!-- collabai:start -->\nold block\n"
                "<!-- collabai:end -->\n\ntail\n", encoding="utf-8")
            self.assertEqual(codex.apply(root), 0)
            text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("# mine", text)
            self.assertIn("tail", text)
            self.assertNotIn("old block", text)
            self.assertIn("--wait", text)
            self.assertEqual(codex.apply(root), 0)


class MetaParkedTests(unittest.TestCase):
    def test_chat_works_with_a_key_and_poster(self):
        # Unparked after the owner-pasted smoke proof (meta-test: ok).
        captured: dict = {}
        with tempfile.TemporaryDirectory() as tmp:
            reply = meta_ai.chat(
                [{"role": "user", "content": "hi"}], Path(tmp),
                poster=_ok_poster(captured), key="LLM_test")
        self.assertEqual(reply, "ready")
        self.assertEqual(captured["model"], "muse-spark-1.3")


def _ok_poster(captured):
    def _post(url, payload, key):
        captured.update(payload)
        return json.dumps(
            {"choices": [{"message": {"content": "ready"}}]}).encode("utf-8")
    return _post


class MetaSmokeTests(unittest.TestCase):
    def test_smoke_bypasses_park_and_uses_muse_model(self):
        captured: dict = {}
        with tempfile.TemporaryDirectory() as tmp:
            reply = meta_ai.smoke_test(
                Path(tmp), poster=_ok_poster(captured), key="LLM_test")
        self.assertEqual(reply, "ready")
        self.assertEqual(captured["model"], "muse-spark-1.3")

    def test_legacy_model_config_is_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / ".collabai" / "config.json"
            cfg.parent.mkdir(parents=True)
            cfg.write_text(json.dumps(
                {"inference": {"model": "meta-spark-1.3"}}), encoding="utf-8")
            self.assertEqual(meta_ai.model_for(root), "muse-spark-1.3")

    def test_http_401_maps_to_key_hint(self):
        import io
        import urllib.error

        def _bad_poster(url, payload, key):
            raise urllib.error.HTTPError(
                url, 401, "Unauthorized", hdrs=None,
                fp=io.BytesIO(b'{"error":"bad key"}'))

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(meta_ai.MetaError) as ctx:
                meta_ai.smoke_test(Path(tmp), poster=_bad_poster, key="bad")
        self.assertIn("401", str(ctx.exception))
        self.assertIn("--meta-key", str(ctx.exception))

    def test_http_429_maps_to_rate_limit(self):
        import io
        import urllib.error

        def _bad_poster(url, payload, key):
            raise urllib.error.HTTPError(
                url, 429, "Too Many", hdrs=None, fp=io.BytesIO(b"slow down"))

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(meta_ai.MetaError) as ctx:
                meta_ai.smoke_test(Path(tmp), poster=_bad_poster, key="k")
        self.assertIn("rate limit", str(ctx.exception))

    def test_empty_content_is_a_clear_error(self):
        def _empty_poster(url, payload, key):
            return json.dumps(
                {"choices": [{"message": {"content": None}}]}).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(meta_ai.MetaError) as ctx:
                meta_ai.smoke_test(Path(tmp), poster=_empty_poster, key="k")
        self.assertIn("empty reply", str(ctx.exception))


class MetaChatLoopTests(unittest.TestCase):
    def test_multi_turn_history_is_resent_and_clear_resets(self):
        import io
        from contextlib import redirect_stdout

        from collabai import harness
        from collabai.harness import _ai_form

        calls: list[list[dict]] = []

        def _fake_chat(messages, root):
            calls.append([dict(m) for m in messages])
            return f"reply-{len(calls)}"

        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(meta_ai, "META_VERIFIED", True), \
                patch.object(meta_ai, "chat", _fake_chat), \
                patch.object(meta_ai, "load_key", lambda: "LLM_test"), \
                redirect_stdout(io.StringIO()):
            _ai_form(Path(tmp), harness._scripted if hasattr(harness, "_scripted")
                     else _scripted(["hello", "follow up", "/clear", "fresh", "/quit"]))
        # Second turn resends first user + assistant turns.
        roles2 = [m["role"] for m in calls[1]]
        self.assertEqual(roles2, ["developer", "user", "assistant", "user"])
        # After /clear, history restarts.
        roles3 = [m["role"] for m in calls[2]]
        self.assertEqual(roles3, ["developer", "user"])


if __name__ == "__main__":
    unittest.main()
