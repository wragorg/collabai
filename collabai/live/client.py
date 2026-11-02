"""Live Share client helpers. Token via env COLLABAI_TOKEN or hidden prompt."""

from __future__ import annotations

import getpass
import json
import os
import urllib.request


def get_token() -> str:
    token = os.environ.get("COLLABAI_TOKEN", "").strip()
    if token:
        return token
    return getpass.getpass("live token: ").strip()


def _req(url: str, token: str, payload: dict | None = None) -> tuple[int, str]:
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except Exception as exc:  # keep CLI simple; surface message only
        return 0, f"request failed: {exc}"


def post_event(port: int, token: str, event: dict) -> tuple[int, str]:
    return _req(f"http://127.0.0.1:{port}/events", token, event)


def fetch_feed(port: int, token: str, since: int = 0) -> tuple[int, str]:
    return _req(f"http://127.0.0.1:{port}/feed?since={since}", token)
