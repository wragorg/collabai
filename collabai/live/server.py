"""Loopback-only Live Share server. Token in memory only, never logged."""

from __future__ import annotations

import hmac
import json
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALLOWED_TYPES = {
    "developer.joined",
    "developer.left",
    "task.started",
    "task.updated",
    "task.completed",
    "module.activity",
    "decision.shared",
}

MAX_BODY = 4096
MAX_EVENTS = 100
SESSION_SECONDS = 15 * 60


def make_token() -> str:
    return secrets.token_urlsafe(32)


def valid_event(obj: object) -> tuple[bool, str]:
    if not isinstance(obj, dict):
        return False, "event must be an object"
    if obj.get("type") not in ALLOWED_TYPES:
        return False, "unknown type"
    for key in ("developer", "task", "area", "status"):
        val = obj.get(key, "")
        if val is None:
            continue
        if not isinstance(val, str):
            return False, f"{key} must be a string"
        if len(val) > 200:
            return False, f"{key} too long"
    for banned in ("code", "diff", "transcript", "prompt", "secret", "token"):
        if banned in obj:
            return False, f"banned field: {banned}"
    return True, ""


class State:
    def __init__(self) -> None:
        self.token = make_token()
        self.expires_at = time.time() + SESSION_SECONDS
        self.events: list[dict] = []
        self.seq = 0

    def expired(self) -> bool:
        return time.time() > self.expires_at

    def add(self, event: dict) -> dict:
        self.seq += 1
        stored = dict(event)
        stored["seq"] = self.seq
        stored["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.events.append(stored)
        if len(self.events) > MAX_EVENTS:
            self.events = self.events[-MAX_EVENTS:]
        return stored


def _authorized(handler: BaseHTTPRequestHandler, state: State) -> bool:
    if state.expired():
        return False
    auth = handler.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    return hmac.compare_digest(auth[7:], state.token)


def _send(handler: BaseHTTPRequestHandler, code: int, obj: dict) -> None:
    body = json.dumps(obj).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def make_handler(state: State):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # noqa: ANN001, ANN202
            pass  # never log tokens or bodies

        def _require_auth(self) -> bool:
            if not _authorized(self, state):
                _send(self, 401, {"error": "unauthorized or expired"})
                return False
            return True

        def do_GET(self):  # noqa: N802
            if not self._require_auth():
                return
            if self.path == "/health":
                _send(self, 200, {"ok": True, "events": len(state.events)})
                return
            if self.path.startswith("/feed"):
                since = 0
                if "since=" in self.path:
                    try:
                        since = int(self.path.split("since=")[1].split("&")[0])
                    except ValueError:
                        since = 0
                items = [e for e in state.events if e.get("seq", 0) > since]
                _send(self, 200, {"events": items})
                return
            _send(self, 404, {"error": "not found"})

        def do_POST(self):  # noqa: N802
            if not self._require_auth():
                return
            if self.path != "/events":
                _send(self, 404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_BODY:
                _send(self, 413, {"error": "body size rejected"})
                return
            try:
                obj = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                _send(self, 400, {"error": "invalid json"})
                return
            ok, reason = valid_event(obj)
            if not ok:
                _send(self, 400, {"error": reason})
                return
            _send(self, 200, {"event": state.add(obj)})

    return Handler


def run_host(port: int = 0) -> int:
    state = State()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    actual = server.server_address[1]
    print("live share active on 127.0.0.1 only. will expire in 15 minutes.")
    print(f"port: {actual}")
    print(f"token: {state.token}")
    print("Share these ONLY with the invited developer over a trusted channel.")
    print("To connect remotely, that developer creates their own SSH tunnel.")
    print("Press Ctrl-C to stop sharing immediately.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    print("live share stopped. token revoked.")
    return 0
