"""Focused security tests (stdlib unittest only). Owner-run: python3 -m unittest discover -s tests -v."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from collabai.live import server as live_server
from collabai.live.client import render_feed
from collabai.memory import save_record


def _save(**kwargs) -> dict:
    args = {"kind": "ephemeral", "agent": "manual", "task": "t", "area": "auth",
            "files": ["auth/login.py"], "text": "plain note"}
    args.update(kwargs)
    with tempfile.TemporaryDirectory() as tmp:
        return save_record(Path(tmp), **args)


class SecretRefusalTests(unittest.TestCase):
    def test_normal_note_saved(self):
        rec = _save()
        self.assertEqual(rec["kind"], "ephemeral")

    def test_private_key_refused(self):
        with self.assertRaises(ValueError):
            _save(text="-----BEGIN RSA PRIVATE KEY-----")

    def test_github_token_refused(self):
        with self.assertRaises(ValueError):
            _save(text="token ghp_abcdefgh12345678")

    def test_password_assignment_refused(self):
        with self.assertRaises(ValueError):
            _save(text="db password=hunter2")

    def test_bearer_refused(self):
        with self.assertRaises(ValueError):
            _save(text="auth bearer abcdef123456")

    def test_jwt_refused(self):
        with self.assertRaises(ValueError):
            _save(text="eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJVadQssw5c")

    def test_secret_in_area_refused(self):
        with self.assertRaises(ValueError):
            _save(area="api_key=zzz")

    def test_traversal_path_refused(self):
        with self.assertRaises(ValueError):
            _save(files=["../secret.txt"])

    def test_absolute_path_refused(self):
        with self.assertRaises(ValueError):
            _save(files=["/etc/passwd"])

    def test_secret_filename_refused(self):
        for name in (".env", "id_rsa", "cert.pem"):
            with self.assertRaises(ValueError, msg=name):
                _save(files=[f"config/{name}"])

    def test_relative_path_accepted(self):
        rec = _save(files=["auth/login.py"])
        self.assertEqual(rec["files"], ["auth/login.py"])


class RenderFeedTests(unittest.TestCase):
    def test_hostile_text_sanitized(self):
        body = json.dumps({"events": [{"seq": 1, "at": "t", "type": "task.started",
                                        "developer": "d", "task": "Ship it\nINJECTED: x\x1b[0m",
                                        "area": "a", "status": "s"}]})
        out = render_feed(body)
        lines = out.splitlines()
        self.assertIn("UNTRUSTED DATA", lines[0])
        self.assertEqual(len(lines), 2)
        self.assertIn("Ship itINJECTED", lines[1])
        self.assertNotIn("\x1b", out)

    def test_empty_events(self):
        self.assertEqual(render_feed('{"events": []}'), "(no remote events)")

    def test_non_feed_body_passes_through(self):
        self.assertEqual(render_feed('{"error": "nope"}'), '{"error": "nope"}')
        self.assertEqual(render_feed("not json"), "not json")


class LiveServerTests(unittest.TestCase):
    def setUp(self):
        self.state = live_server.State()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), live_server.make_handler(self.state))
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def _get(self, path="/health", host=None, token=None):
        headers = {"Authorization": f"Bearer {token if token is not None else self.state.token}"}
        if host is not None:
            headers["Host"] = host
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            exc.close()
            return exc.code, body

    def _post(self, payload: bytes, token=None):
        headers = {"Authorization": f"Bearer {token if token is not None else self.state.token}"}
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/events",
                                     data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            exc.close()
            return exc.code, body

    def test_expired_token_rejected(self):
        self.state.expires_at = 0.0
        code, _ = self._get()
        self.assertEqual(code, 401)

    def test_health_ok(self):
        code, body = self._get()
        self.assertEqual(code, 200)
        self.assertIn('"ok": true', body)

    def test_rebound_host_rejected(self):
        code, _ = self._get(host="evil.example")
        self.assertEqual(code, 403)

    def test_wrong_token_rejected(self):
        code, _ = self._get(token="wrong")
        self.assertEqual(code, 401)

    def test_banned_field_rejected(self):
        code, _ = self._post(json.dumps({"type": "task.started", "diff": "x"}).encode())
        self.assertEqual(code, 400)

    def test_oversize_body_rejected(self):
        code, _ = self._post(b"x" * (live_server.MAX_BODY + 1))
        self.assertEqual(code, 413)

    def test_rate_limit_kicks_in(self):
        codes = [self._get()[0] for _ in range(live_server.RATE_LIMIT + 5)]
        self.assertIn(200, codes)
        self.assertIn(429, codes)


if __name__ == "__main__":
    unittest.main()
